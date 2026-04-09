# 模块 9：Persistent Sandbox 冷存快照与恢复

## 模块目标

这个模块描述 `persist=true` 的 direct sandbox 如何在 **保留工作区数据** 的前提下释放 live disk，把状态切到 `cold`，并在下一次 `start` 时自动从 snapshot 恢复出新的 PVC/PV。

当前实现主要落在：

- `treadstone/models/sandbox.py`
- `treadstone/models/metering.py`
- `treadstone/services/sandbox_service.py`
- `treadstone/services/storage_snapshot_orchestrator.py`
- `treadstone/services/k8s_sync.py`
- `treadstone/api/sandboxes.py`
- `deploy/cluster-storage/templates/volumesnapshotclass.yaml`

## 1. 产品模型

这一版实现采用的是 **sandbox 绑定式 cold snapshot**，而不是独立 snapshot 资源模型。

对用户来说，公开对象仍然只有 `sandbox`：

- 用户不会单独管理 snapshot 列表
- 每个 persistent direct sandbox 在任意时刻最多只绑定一份 cold snapshot
- `snapshot` 的含义固定为：
  - 若当前 `ready`，先停机
  - 对 workspace PVC 做快照
  - 显式删除 Sandbox CR 和 workspace PVC
  - sandbox 进入 `cold`
- `start` 对 `cold` sandbox 的含义固定为：
  - 自动从绑定 snapshot 恢复 live disk
  - 等待恢复后的 sandbox 重新 `ready`

当前产品面不再公开 `restore-only`。原因是 ACK 当前依赖 `WaitForFirstConsumer`，而“只恢复磁盘、不启动 workload”会天然和 `replicas=0` 冲突，带来额外分支和隐式临时行为。为降低状态复杂度和测试面，公开恢复入口收敛为：

- `cold -> start`

这让用户只需要理解一件事：

- `stopped` 代表磁盘还挂着，恢复快
- `cold` 代表磁盘已经释放，恢复更慢但更省钱、调度更灵活

## 2. 当前公开状态与字段

### 主状态

当前 `Sandbox.status` 包括：

- `creating`
- `ready`
- `stopped`
- `cold`
- `error`
- `deleting`

其中 `cold` 表示：

- 没有 live PVC / PV / disk
- 仍然保留一份可恢复的 cold snapshot
- 继续占用 storage quota，但不占用 compute

### 异步操作覆盖层

为了避免把“后台正在做 snapshot / restore”混进主状态机，这次实现新增了 `pending_operation`：

- `snapshotting`
- `restoring`

它是对主状态的覆盖层，不是新的生命周期终态。

### 新增存储元数据

当前 `Sandbox` 行会额外记录：

- `storage_backend_mode`
- `k8s_workspace_pvc_name`
- `k8s_workspace_pv_name`
- `workspace_volume_handle`
- `workspace_zone`
- `snapshot_provider_id`
- `snapshot_k8s_volume_snapshot_name`
- `snapshot_k8s_volume_snapshot_content_name`
- `gmt_snapshotted`
- `gmt_restored`
- `gmt_snapshot_archived`（仅预留，v1 未启用）

API 返回里新增：

- `pending_operation`
- `storage.mode`
- `storage.size`
- `storage.snapshot_created_at`
- `storage.zone`

## 3. 当前公开接口

在原有 sandbox CRUD 之上，这次只保留一个新增接口：

- `POST /v1/sandboxes/{sandbox_id}/snapshot`

并扩展了：

- `POST /v1/sandboxes/{sandbox_id}/start`

当前语义如下：

### `POST /snapshot`

只支持：

- `persist=true`
- `provision_mode="direct"`

状态约束：

- `ready`：先走 stop，再进入 `snapshotting`
- `stopped`：直接进入 `snapshotting`
- `cold` / `deleting` / `creating` / 已有 `pending_operation`：返回 `409`

### `POST /start`

当前有两条路径：

- `stopped|error`：沿用原来的 scale-up
- `cold`：走 `restore_on_start`

即：

- 先进入 `pending_operation="restoring"`
- 后台从 snapshot 恢复 PVC/PV 和 Sandbox CR
- 恢复成功后直达 `ready`

当前不再提供：

- `POST /v1/sandboxes/{sandbox_id}/restore`
- CLI `treadstone sandboxes restore`
- Web “Restore Only” 按钮

## 4. Kubernetes 与 ACK 实现方式

这次实现的产品模型是云无关的，但 v1 provider 是 ACK-first。

### 通用 K8s 能力

真正依赖的 Kubernetes 通用接口包括：

- `VolumeSnapshotClass`
- `VolumeSnapshot`
- `VolumeSnapshotContent`
- `PersistentVolumeClaim.spec.dataSource`
- `WaitForFirstConsumer`

### ACK-first 的具体落地

当前默认 snapshot class 配置是：

- `TREADSTONE_SANDBOX_VOLUME_SNAPSHOT_CLASS=treadstone-workspace-snapshot`

Helm 增加了：

- `deploy/cluster-storage/templates/volumesnapshotclass.yaml`

RBAC 新增权限：

- `volumesnapshots`
- `volumesnapshotcontents`
- `volumesnapshotclasses`
- `persistentvolumeclaims`
- `persistentvolumes`

这一版还没有直接调用 ECS API 做 snapshot import/export；v1 的 cold asset 是 **保留的 K8s VolumeSnapshot 对象**，并把 provider handle 记录在 `snapshot_provider_id`。

## 5. 快照与恢复链路

### Snapshot 链路

后台编排器是 `StorageSnapshotOrchestrator`，它按下面的顺序推进：

1. 校验 `VolumeSnapshotClass` 存在
2. 如果是 `ready` 发起的 snapshot，先等待 CR 真正进入 `STOPPED`
3. 从 workspace PVC 创建 `VolumeSnapshot`
4. 等待 snapshot `readyToUse=true`
5. 读取 `VolumeSnapshotContent.status.snapshotHandle`
6. 显式删除 Sandbox CR
7. 显式删除 workspace PVC
8. 确认 CR/PVC/PV 都已消失
9. 把 sandbox 切到：
   - `status=cold`
   - `storage_backend_mode=standard_snapshot`
   - `pending_operation=null`

这里有两个刻意的实现细节：

- 不依赖 agent-sandbox 的隐式 shutdown 语义去回收磁盘
- 必须同时满足“快照 ready”和“live disk 确认释放”才允许 cutover 到 `cold`

### Restore-on-start 链路

恢复路径复用 direct sandbox 创建逻辑，但 `volumeClaimTemplates` 会带上：

- `spec.dataSource.kind=VolumeSnapshot`
- `spec.dataSource.apiGroup=snapshot.storage.k8s.io`

恢复顺序是：

1. `start(cold)` 把 sandbox 置为 `pending_operation=restoring`
2. 编排器创建新的 direct Sandbox CR，`replicas=1`
3. `workspace` PVC 从绑定 snapshot 恢复
4. 等待 PVC/PV materialize
5. 等待恢复出的 Sandbox CR 进入 `READY`
6. 切回：
   - `status=ready`
   - `storage_backend_mode=live_disk`
   - `pending_operation=null`
7. 尝试删除旧的 bound snapshot

## 6. 失败补偿与已知边界

### 1. 不会对还没真正停稳的 sandbox 做 snapshot

`snapshot(ready)` 不再只是“发出 stop 请求后立刻快照”。

后台会先读真实 Sandbox CR：

- 如果 K8s 还显示 `READY`
- 或者还在 `creating`

那么只会继续等待，不会创建 `VolumeSnapshot`。

### 2. restore 后遗留的旧 snapshot 不会被错误复用

如果 restore 成功但旧 snapshot 清理失败，sandbox 会回到 `live_disk`，但保留 snapshot binding。

这时候下一次再做 `snapshot`，当前实现会先尝试清理旧 snapshot：

- 清理成功：再创建新 snapshot
- 清理失败：本次 snapshot 直接失败，保持 `stopped/live_disk`

不会把旧 snapshot 当成“新的冷存点”继续复用。

### 3. restore 遇到运行时错误不会无限卡在 `restoring`

`k8s_sync` 在 `pending_operation` 期间会抑制普通状态回写，因此 restore 不能依赖 sync loop 自动把 `ERROR` 写回 DB。

当前实现里，编排器会显式处理恢复期的 `ReconcilerError`：

- 如果工作盘已经 materialize，但恢复出的 runtime 报错
- sandbox 会回落到 `stopped/live_disk`
- 用户可以重新点 `start`

### 4. 删除 live-disk sandbox 时，bound snapshot 清理失败不会再伪装成删除成功

delete 路径会先尝试清理残留的 bound snapshot。

如果 snapshot 清理失败：

- 不会继续删 live CR/PVC
- sandbox 会被标成 `error`
- API 返回 `409`

因此不会出现“接口返回 204，但后台留下孤儿 snapshot”的情况。

## 7. Metering 与 quota 语义

这次没有引入新的 quota 资源类型，仍然沿用已有 `StorageLedger`。

但 `StorageLedger` 新增了：

- `backend_mode`

它和 sandbox 的 `storage_backend_mode` 对齐，当前值可能是：

- `live_disk`
- `standard_snapshot`

这意味着：

- `cold` sandbox 仍然占用 storage quota
- 只有真正 `delete sandbox` 才 release storage ledger
- 但冷存后不再占用 compute session

## 8. 后台循环与状态同步

为避免把 provider 级 snapshot 状态机塞进已有 metering/lifecycle loop，这次单独新增了 storage snapshot tick：

- 单副本模式：`treadstone/main.py`
- 多副本模式：`LeaderControlledSyncSupervisor`

它只负责扫描：

- `pending_operation=snapshotting`
- `pending_operation=restoring`

并推进 cold storage 编排。

同时 `k8s_sync` 这次有两个重要约束：

- `cold` 被视为“CR 缺失也合法”
- `pending_operation` 非空时，watch/reconcile 不会覆盖 orchestrator 正在推进的状态

## 9. 当前边界

这一版明确只实现了下面这组能力：

- 只支持 `persist=true` 的 direct sandbox
- 只支持单 workspace 卷
- 只支持一份绑定 snapshot
- 不支持 clone / fork
- 不支持多历史恢复点
- 不支持跨 sandbox 恢复点复用
- `archive_snapshot` 只在 schema 里预留，功能未启用

因此它解决的是：

- 持久 sandbox 的冷存与恢复
- live disk 成本释放
- 从“绑定在原 AZ 的 PVC”切到“从 snapshot 重新 materialize 的 PVC”

但它还不是“完全透明的 Neon 风格 auto-resume 平台”。后续如果继续演进，顺序仍然建议是：

1. `auto-stop`
2. `auto-snapshot-to-cold`
3. `auto-archive`
4. `auto-delete`
5. 代理入口透明恢复

## 10. 2026-04-09 白盒测试记录

这一轮测试的目标，是在删除 `restore-only` 之后验证新的单入口模型是否闭环，并检查是否仍残留旧的公开面和内部状态字段。

白盒覆盖点包括：

- `snapshot(ready)` 是否仍会先等待真实 CR 停稳
- `cold -> start -> restoring -> ready` 是否仍能完成
- 恢复期 runtime 报错是否会回落到 `stopped/live_disk`
- Web / CLI / API / OpenAPI 是否已经删掉 `/restore`
- 模型和迁移是否已经移除 `pending_operation_target_status`

本轮详细测试结果会在完成全量回归后继续追加到本节末尾。

### 本轮结果

- `make test`：`775 passed, 1 skipped, 7 deselected`
- `make lint`：通过
- `make gen-openapi`：通过
- `make gen-web-types`：通过
- `make gen-sdk-python`：通过
- `cd web && npm run build`：通过

### 这轮白盒检查实际覆盖到的内部细节

- **API / OpenAPI / SDK / Web / CLI 收口**
  - 生成后的 `openapi.json`、`openapi-public.json`、`web/src/api/schema.d.ts`、`sdk/python/` 已不再暴露 `/v1/sandboxes/{sandbox_id}/restore`
  - Web 页面和 CLI 已删掉 `Restore Only` / `treadstone sandboxes restore`
  - 测试里保留了一条显式 `404` 校验，确保后续不会误把这个路由加回来
- **数据库与状态机**
  - `Sandbox` 模型已移除 `pending_operation_target_status`
  - 新迁移 `4b3f2f3fd7d8_remove_restore_only_target_status.py` 会在 drop column 前，把旧的 `restore-only` 进行中记录重置回 `cold`
  - 单测继续覆盖 `pending_operation=snapshotting|restoring` 的推进和 `StorageLedger.backend_mode` 的切换
- **恢复路径**
  - `test_start_on_cold_restores_and_returns_to_ready` 继续校验唯一公开恢复入口 `cold -> start -> ready`
  - `test_restore_tick_falls_back_to_stopped_live_disk_when_runtime_errors` 继续校验恢复期 runtime 出错时，不会卡死在 `restoring`
- **快照路径**
  - `test_snapshot_tick_waits_for_stop_before_creating_snapshot` 继续校验不会对仍在运行的 sandbox 直接做快照
  - `test_snapshot_tick_fails_instead_of_reusing_stale_bound_snapshot` 继续校验旧 snapshot 清理失败时不会被错误复用
  - `test_snapshot_tick_completes_cold_cutover_after_cleanup_finishes_on_later_tick` 继续校验只有快照 ready 且 live disk 真正释放后才切到 `cold`
- **资源删除**
  - `test_delete_cold_sandbox_deletes_snapshot_and_releases_storage_ledger` 继续校验删除 cold sandbox 时会删除绑定 snapshot 并释放 storage ledger
  - `test_delete_returns_409_when_bound_snapshot_cleanup_fails` 继续校验 bound snapshot 清理失败时不会伪装成删除成功

### 当前残留边界

- `restore-only` 已经从产品面删除，但测试里仍保留 `POST /restore -> 404` 作为防回归检查，这属于预期。
- 这轮验证依然是本地白盒回归，不包含真实 ACK 集群上的在线 `VolumeSnapshot` / ECS 云盘恢复压测；真实云环境仍需用 staging 或 production disposable sandbox 再做一次端到端验收。

### 额外白盒脚本观察

除了 pytest 回归，这轮还额外跑了两条白盒脚本，直接打印编排日志以及内存数据库里的 `Sandbox` / `StorageLedger` 状态。

#### 成功路径

观察到的关键切换如下：

- 初始 `ready/live_disk`：K8s 有 CR、PVC 已 `Bound`、DB 里的 ledger 是 `live_disk`
- `POST /snapshot` 之后：DB 立刻变成 `stopped + snapshotting`，K8s `replicas=0`，PVC 仍保留
- 第 1 个 tick：日志出现 `Creating cold snapshot ...`，DB 写入 `snapshot_k8s_volume_snapshot_name`、`k8s_workspace_pvc_name`、`k8s_workspace_pv_name`、`workspace_zone`
- 第 2 个 tick：日志出现 `Cold snapshot became ready` 与 `Cold snapshot cutover completed`，DB 切到 `cold/standard_snapshot`，PVC/PV 字段清空，ledger 同步切到 `standard_snapshot`
- `POST /start` 之后：DB 变成 `cold + restoring`
- 第 1 个 restore tick：重新创建 `replicas=1` 的 Sandbox CR，PVC 已重新 `Bound`，但 DB 仍保持 `cold + restoring`
- 第 2 个 restore tick（手工把 fake CR 置为 ready 后）：DB 切到 `ready/live_disk`，bound snapshot 被清掉，ledger 回到 `live_disk`

这证明当前唯一公开恢复入口 `cold -> start` 的底层资产切换顺序是闭环的，而且 snapshot 不会在恢复完成前被提前删除。

#### 失败路径

第二条脚本在 restore 过程中强行注入 `ReconcilerError`，观察结果是：

- DB 最终回落到 `stopped/live_disk`
- `pending_operation` 被清空
- `status_message` 保留底层错误 `restore failed`
- bound snapshot 被清掉
- ledger 回到 `live_disk`

这和当前失败补偿设计一致，说明删除 `restore-only` 之后，恢复期的 runtime 错误仍然不会把 sandbox 卡死在 `cold + restoring`。

#### 脚本环境说明

这两条脚本为了避免最小化 fixture 缺少 `TierTemplate` 而被 metering enforcement 拦住，临时关闭了 `metering_enforcement_enabled`。这只影响脚本 harness，不影响前面已经通过的正常单测、API 测试和全量 `make test` 回归。
