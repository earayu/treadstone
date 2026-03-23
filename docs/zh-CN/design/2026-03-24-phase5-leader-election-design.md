# Phase 5: 多副本 K8s Watch Leader Election 设计

**日期：** 2026-03-24

**关联 Issue：** [#15 feat: implement Leader Election for multi-replica K8s Watch](https://github.com/earayu/treadstone/issues/15)

**关联设计：**
- `docs/zh-CN/design/2026-03-17-phase2-sandbox-orchestration.md` §11 K8s 状态同步
- `docs/zh-CN/design/2026-03-19-phase2-sandbox-api-implementation.md`

---

## 1. 背景

当前 Treadstone 在 FastAPI `lifespan` 中启动一个后台同步循环：

- `Watch`：监听 `Sandbox` CR 变化并把状态写回 DB
- `Reconciliation`：定期 `List + compare`，修正漏掉的状态

这个设计在单副本下成立，但在多副本部署下会出现一个问题：每个副本都会各自启动一份后台同步循环。结果是：

- 同一个 K8s 事件会被处理 N 次
- K8s API Server 会收到 N 条 Watch 连接
- 多个副本会同时跑 Reconciliation，造成重复 `List + DB update`
- 即使有 `version` 乐观锁兜底，也会放大日志噪音和系统负载

Phase 2 设计文档已经在 §11.6 明确写出这个约束：水平扩展前必须先实现 Leader Election。

---

## 2. 目标与非目标

### 2.1 目标

- 确保任意时刻只有一个 Treadstone 副本运行 `Watch + Reconciliation`
- 非 leader 副本继续正常提供 HTTP API
- leader 崩溃后，其他副本能在可接受时间内自动接管
- 不引入 Redis 等新的基础设施依赖
- 与现有 `kr8s` 客户端、Helm chart、RBAC 体系兼容

### 2.2 非目标

- 不把后台同步从 API Server 中拆成独立 worker Deployment
- 不解决现有历史脏数据、跨环境数据库混用等问题
- 不实现跨集群 Leader Election
- 不为所有后台任务统一抽象一个通用分布式调度框架

---

## 3. 方案选择

### 3.1 备选方案

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| K8s Lease | 使用 `coordination.k8s.io/v1` `Lease` 对象选主 | 原生 K8s，无新依赖；适合当前部署模型 | 需要补充 Lease RBAC 和少量控制逻辑 |
| Redis 分布式锁 | 使用 `SET NX EX` / Redlock | 逻辑直观，也可用于非 K8s 场景 | 新增 Redis 依赖；当前项目没有 Redis |

### 3.2 结论

选择 **K8s Lease-based Leader Election**。

原因：

- Treadstone 的生产环境本来就运行在 Kubernetes 中
- 当前同步任务本身强依赖 K8s API；用 K8s 自己的 Lease 最自然
- 避免为了一个后台互斥场景引入 Redis
- 与 Issue #15 的推荐方向一致

---

## 4. 总体架构

```
Treadstone Pod
  │
  ├── HTTP API
  │     └── 始终可用（leader / follower 都提供）
  │
  └── Leader Supervisor
        │
        ├── Lease Elector
        │     ├── 尝试创建 / 获取 Lease
        │     ├── leader 周期性 renew
        │     └── follower 周期性重试 acquire
        │
        └── Sync Runner
              ├── 成为 leader → 启动 start_sync_loop()
              ├── 失去 leadership → cancel sync task
              └── shutdown → best-effort release Lease
```

核心原则：

- **只有 leader 拥有同步循环**
- **leader election 与 sync loop 解耦**
- **HTTP 服务不依赖 leadership**

---

## 5. 详细设计

### 5.1 Lease 对象

每个环境维护一个 namespaced Lease，例如：

```yaml
apiVersion: coordination.k8s.io/v1
kind: Lease
metadata:
  name: treadstone-sync-leader
  namespace: treadstone-prod
spec:
  holderIdentity: treadstone-prod-treadstone-749fd87b95-jwkts
  leaseDurationSeconds: 15
  acquireTime: "2026-03-24T03:00:00Z"
  renewTime: "2026-03-24T03:00:10Z"
  leaseTransitions: 3
```

约定：

- `holderIdentity` 使用 Pod 唯一标识，优先取 `TREADSTONE_POD_NAME`，回退到 `HOSTNAME`
- Lease 名称通过配置控制，默认 `treadstone-sync-leader`
- Lease 所在 namespace 默认取当前 Pod namespace；MVP 下可与 `settings.sandbox_namespace` 保持一致

### 5.2 新增配置

建议新增以下配置：

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `leader_election_enabled` | `false` | 是否启用 Leader Election |
| `leader_election_lease_name` | `treadstone-sync-leader` | Lease 名称 |
| `leader_election_lease_duration_seconds` | `15` | Lease TTL |
| `leader_election_renew_interval_seconds` | `5` | leader 续约周期 |
| `leader_election_retry_interval_seconds` | `2` | follower 重试获取周期 |
| `pod_name` | `""` | 当前 Pod 名称，来自 downward API |
| `pod_namespace` | `""` | 当前 Pod namespace，来自 downward API |

约束：

- `renew_interval_seconds < lease_duration_seconds`
- `retry_interval_seconds <= renew_interval_seconds`

### 5.3 运行时组件

建议新增两个组件：

#### A. `LeaderElector`

职责：

- 与 K8s Lease API 交互
- 负责 `acquire / renew / observe loss`
- 暴露当前 leadership 状态

#### B. `LeaderControlledSyncSupervisor`

职责：

- 在获得 leadership 后启动 `start_sync_loop(...)`
- 在 leadership 丢失时取消该 task
- 在应用退出时关闭 supervisor 和 sync task

这样 `start_sync_loop()` 本身不需要感知选主逻辑，仍保持“只管同步”的单一职责。

### 5.4 获取与续约算法

#### 5.4.1 获取 Lease

每个副本循环执行：

1. `GET Lease`
2. 如果 Lease 不存在：
   - `CREATE Lease(holderIdentity=self)`
   - 创建成功则成为 leader
   - 如果创建返回 `409 Conflict`，说明别的副本抢先创建，进入下一轮
3. 如果 Lease 已存在：
   - 若 `holderIdentity == self`，执行 renew
   - 若 Lease 已过期，尝试基于 `resourceVersion` 更新为自己
   - 若 Lease 未过期且持有者不是自己，保持 follower

#### 5.4.2 Lease 过期判断

使用：

```text
effective_renew_time = spec.renewTime or spec.acquireTime
expired = now_utc - effective_renew_time >= leaseDurationSeconds
```

若 `renewTime` 和 `acquireTime` 都缺失，视为过期脏 Lease，可抢占。

#### 5.4.3 Renew

leader 每 `renew_interval_seconds` 更新：

- `spec.holderIdentity`
- `spec.renewTime`
- `spec.leaseDurationSeconds`

若 renew 失败，进入快速重试；连续失败直到下一次 loop 发现自己不再持有 Lease 时，触发 leadership lost。

### 5.5 生命周期集成

当前逻辑是在 `lifespan()` 中直接：

```python
sync_task = asyncio.create_task(start_sync_loop(...))
```

改为：

```python
supervisor = LeaderControlledSyncSupervisor(...)
leader_task = asyncio.create_task(supervisor.run())
```

行为变化：

- `leader_election_enabled = false`
  - 保持现有行为，直接启动 sync loop
- `leader_election_enabled = true`
  - 只在本实例成为 leader 后才启动 sync loop
  - leadership lost 时取消 sync loop

### 5.6 leadership 丢失处理

以下情况都视为失去 leadership：

- Lease 被其他副本抢占
- renew 连续失败，且下一轮检查发现 Lease 持有者不是自己
- K8s API 长时间异常，无法确认自己仍然持有 Lease

处理策略：

1. 记录 `leader_lost` 日志
2. 取消当前 `sync_task`
3. 等待 supervisor 下一轮重新参与竞争

这里的设计原则是宁可短暂没有 leader，也不要让旧 leader 在不确定状态下继续跑同步。

### 5.7 优雅退出

Pod 收到 `SIGTERM` / FastAPI shutdown 时：

1. 取消 `sync_task`
2. 如果自己是 leader，best-effort release Lease

release 方式：

- 首选：将 `holderIdentity` 清空并更新 `renewTime`
- 失败时不阻塞退出，依赖 Lease TTL 自动过期

不建议直接 `DELETE Lease`，因为：

- 删除和重建会增加竞争窗口
- Lease 对象可以复用，保留 `leaseTransitions` 更利于排障

### 5.8 Split-Brain 风险与兜底

Leader Election 不能绝对消除瞬时双 leader 窗口，例如：

- 网络抖动导致旧 leader 误以为自己仍然有效
- 新 leader 已抢占成功，旧 leader 尚未感知

风险控制：

- Lease 更新依赖 `resourceVersion`，避免无限覆盖
- 旧 leader 一旦 renew 失败或发现自己不再持有 Lease，立即 cancel sync loop
- 现有 DB `version` 乐观锁仍作为最后一道防线
- 周期性 Reconciliation 继续保留，用于修正短暂不一致

因此，这个方案把“双 leader 窗口”收敛为短暂、可恢复、可观测的问题。

---

## 6. K8s 与 Helm 变更

### 6.1 RBAC

在现有 `ClusterRole` 中新增 Lease 权限：

```yaml
- apiGroups:
    - coordination.k8s.io
  resources:
    - leases
  verbs:
    - get
    - list
    - watch
    - create
    - update
    - patch
```

不需要 `delete`。

### 6.2 Deployment 环境变量

通过 downward API 注入：

```yaml
env:
  - name: TREADSTONE_POD_NAME
    valueFrom:
      fieldRef:
        fieldPath: metadata.name
  - name: TREADSTONE_POD_NAMESPACE
    valueFrom:
      fieldRef:
        fieldPath: metadata.namespace
```

同时从 values 注入：

- `TREADSTONE_LEADER_ELECTION_ENABLED`
- `TREADSTONE_LEADER_ELECTION_LEASE_NAME`
- `TREADSTONE_LEADER_ELECTION_LEASE_DURATION_SECONDS`
- `TREADSTONE_LEADER_ELECTION_RENEW_INTERVAL_SECONDS`
- `TREADSTONE_LEADER_ELECTION_RETRY_INTERVAL_SECONDS`

### 6.3 Values 策略

建议：

- `values.yaml`：默认 `leaderElection.enabled = false`
- `values-local.yaml`：保持 `false`
- `values-prod.yaml`：显式 `true`
- `values-demo.yaml`：如果未来恢复 demo 环境，可保持 `false` 或按实际副本数开启

这样本地开发不依赖 K8s Lease，生产多副本默认安全。

---

## 7. 可观测性

至少补充以下日志：

- `leader election enabled/disabled`
- `leadership acquired`
- `leadership renewed`
- `leadership lost`
- `leadership released`
- `failed to acquire lease`
- `failed to renew lease`

建议后续补充指标，但不作为本次范围硬要求：

- `treadstone_leader_election_is_leader`
- `treadstone_leader_election_acquire_total`
- `treadstone_leader_election_renew_fail_total`
- `treadstone_sync_loop_running`

---

## 8. 测试策略

### 8.1 单元测试

新增：

- `tests/unit/test_leader_election.py`
  - 空 Lease 时成功 acquire
  - 已持有 Lease 时成功 renew
  - 他人持有且未过期时保持 follower
  - Lease 过期后成功抢占
  - `409 Conflict` 时重试失败但不误判 leader
- `tests/unit/test_main_lifespan.py` 或 `tests/unit/test_sync_supervisor.py`
  - leader 才会启动 `start_sync_loop`
  - leadership lost 时会 cancel sync task
  - feature flag 关闭时保留旧行为

### 8.2 Helm / 配置验证

- `helm template` 验证 Lease 相关 env 和 RBAC 正确渲染
- 确认 `values-prod.yaml` 开启 leader election

### 8.3 集群验证

在实际 K8s 环境中验证：

1. 部署 2 个副本
2. `kubectl get lease -n <ns>` 确认只有一个 holder
3. 查看两个 Pod 日志，确认只有 leader 启动 sync loop
4. 删除 leader Pod，确认 follower 在一个 Lease TTL 内接管

---

## 9. 发布与回滚

### 9.1 发布建议

1. 先发布带 feature flag 的版本
2. 在生产配置中开启 `leaderElection.enabled=true`
3. 观察 Lease、日志和 Watch 稳定性
4. 再扩大副本或开启 HPA

### 9.2 回滚策略

如果 Leader Election 本身异常：

- 可通过环境变量关闭 `leader_election_enabled`
- 暂时回到单副本运行模式

这保证故障面只影响后台同步互斥，不会阻断 API 服务本身。

---

## 10. 结论

对于 Treadstone 当前的架构，**K8s Lease 是最合适的多副本选主方案**：

- 不新增外部依赖
- 与现有 K8s/Helm/RBAC 架构天然兼容
- 能把 `Watch + Reconciliation` 严格收敛到单 leader
- 即使存在短暂 split-brain，也有 Lease CAS、任务取消和 DB 乐观锁多层兜底

因此，Leader Election 应作为 **Phase 5 生产化的前置能力**，在继续放大副本数和 HPA 之前完成。
