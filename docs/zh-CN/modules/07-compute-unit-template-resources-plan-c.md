---
name: CU formula and template fix
overview: 将 CU 公式从 max(vCPU, memory/divisor) 改为加权累加 CPU_WEIGHT * vCPU + MEMORY_WEIGHT * memory_gib；全面重新设计模板 request/limit 资源规格（方案 C），修复 tiny OOM，利用 limit 作为商业差异化武器。Tier 月度额度暂不调整。
todos:
  - id: cu-formula
    content: "Part 1: metering_helpers.py 删 CU_MEMORY_GIB_DIVISOR，新增 CPU_WEIGHT + MEMORY_WEIGHT，重写 calculate_cu_rate；同步改 metering_service.py 和 usage.py 中的内联公式"
    status: pending
  - id: template-helm
    content: "Part 2a: 四份 Helm values 全量重写 CPU/Memory 规格（按方案 C 表）；改 sandbox-templates.yaml liveness 探针"
    status: pending
  - id: template-python
    content: "Part 2b: metering_helpers.py TEMPLATE_SPECS tiny memory_gib 0.5→1；k8s_client.py FakeK8sClient tiny 512Mi→1Gi"
    status: pending
  - id: tests
    content: "Part 3: 更新 test_metering_models、test_usage_api、test_metering_tasks 中的 CU 期望值"
    status: pending
  - id: docs
    content: "Part 4: 更新 README、getting-started、中文审计/运维文档中的公式和模板表"
    status: pending
  - id: tier-limits
    content: "Part 5: Tier 月度额度暂不调整（用户明确要求）"
    status: cancelled
isProject: false
---

# CU 公式改造 + 模板资源修复

## 背景

- 集群中 `aio-sandbox-tiny` 的 warm pool Pod 因 **memory limit = 512Mi** 而频繁 OOMKilled（稳态约 630-720Mi）
- 当前 CU 公式 `max(vCPU, memory_GiB / 2)` 使用 `max` 语义，改为**加权累加**更贴近真实成本、且参数可调
- 当前没有线上用户，是改计费模型成本最低的时期

## Part 1: CU 公式 — 从 `max` 改为加权累加

**新公式：**

```
CU/hour = CPU_WEIGHT * vCPU_request + MEMORY_WEIGHT * memory_GiB_request
```

**初始参数：** `CPU_WEIGHT = 1.0`, `MEMORY_WEIGHT = 0.125`

**新 CU 费率对照：**

- tiny (0.25 vCPU, 1 GiB): **0.375** CU/h (原 0.25)
- small (0.5 vCPU, 1 GiB): **0.625** CU/h (原 0.5)
- medium (1 vCPU, 2 GiB): **1.25** CU/h (原 1.0)
- large (2 vCPU, 4 GiB): **2.5** CU/h (原 2.0)
- xlarge (4 vCPU, 8 GiB): **5.0** CU/h (原 4.0)

### 需改的文件

**核心公式（3 处）：**

- [treadstone/services/metering_helpers.py](treadstone/services/metering_helpers.py) — 删除 `CU_MEMORY_GIB_DIVISOR`，新增 `CPU_WEIGHT` + `MEMORY_WEIGHT`；重写 `calculate_cu_rate` 为 `CPU_WEIGHT * vcpu + MEMORY_WEIGHT * memory_gib`
- [treadstone/services/metering_service.py](treadstone/services/metering_service.py) L799-801 — `get_compute_unit_hours_for_period` 中的内联公式同步改为加权累加
- [treadstone/api/usage.py](treadstone/api/usage.py) L49 — `_serialize_session` 中的内联公式同步改

**不需改（已间接引用 `calculate_cu_rate`）：**

- `metering_tasks.py` L104 和 `metering_service.py` L412 已通过调用 `calculate_cu_rate()` 使用公式，无需额外改动

## Part 2: 模板资源全面重新设计（方案 C）

### 前提分析

**集群规格：** 3 节点 x 16 CPU x ~28.5 GiB allocatable（ACK 香港区）

**镜像特性：** 内存密集型。`ghcr.io/agent-infra/sandbox:latest` 包含 supervisord + nginx + code-server + Jupyter + Chromium + VNC + MCP 等十余进程。`kubectl top` 实测空闲 Pod 稳态约 **630-720Mi**，CPU 仅 **14m**。镜像有较高的内存底座但 CPU 几乎不用；真正消耗 CPU 的是用户主动触发的编译/浏览器/脚本执行。

**典型 workload：**

- AI Agent 执行代码（脚本、pip install、编译）
- 浏览器自动化（Chromium headless/headed，每 tab ~100-300Mi）
- VS Code (code-server) 远程开发（活跃时 ~200-500Mi）
- Jupyter notebook（取决于数据量）

**设计原则：**

1. **Request** = 计量依据 + 调度保证，设为典型持续负载
2. **Limit** = 硬天花板，作为**商业差异化武器**：低档位 limit 紧，制造升级动力；中档位 limit 慷慨，奖励付费用户
3. **内存密集型镜像**：所有档位必须保证至少 1Gi request（镜像底座 ~700Mi）
4. **小集群友好**：xlarge limit 不超过单节点 32%

### 方案 C 总表

```
                  CPU                    Memory                         CU/h
Tier       req     lim           req       lim         burst倍率        (新公式)
──────────────────────────────────────────────────────────────────────────────
tiny       250m    500m          1Gi       1200Mi      1.17x            0.375
small      500m    1000m         1Gi       2Gi         2.0x             0.625
medium     1       1500m         2Gi       3Gi         1.5x             1.25
large      2       2500m         4Gi       5Gi         1.25x            2.5
xlarge     4       5             8Gi       9Gi         1.125x           5.0
```

### 逐档设计理由

#### Tiny — "能用，但会想要更多"（入口档）


| 参数      | 值      | 理由                                                                            |
| ------- | ------ | ----------------------------------------------------------------------------- |
| CPU req | 250m   | 空闲仅 14m，250m 足够保证调度和轻量脚本执行                                                    |
| CPU lim | 500m   | 2x burst，允许短时编译/安装包的 CPU 峰值                                                   |
| Mem req | 1Gi    | 镜像底座 ~700Mi，1Gi 是能稳定运行的最低线。同时也是 metering 依据                                   |
| Mem lim | 1200Mi | **刻意偏紧**。仅给 ~200Mi 用户空间（Chrome 一开就感受到压力）。商业策略：让用户体验到"能用但不够舒服"，产生升级到 Small 的动力 |
| CU/h    | 0.375  | 性价比最高的档位（每 CU 可获得 3.2 GiB limit），适合脚本/Agent 短任务                               |


#### Small — "升级就能感受到区别"（性价比甜蜜点）


| 参数      | 值     | 理由                                                                                                                                |
| ------- | ----- | --------------------------------------------------------------------------------------------------------------------------------- |
| CPU req | 500m  | 2x tiny，足够支撑轻量编译和 code-server 交互                                                                                                  |
| CPU lim | 1000m | 2x burst，覆盖中等编译峰值                                                                                                                 |
| Mem req | 1Gi   | **和 Tiny 相同**。CU 差价完全来自 CPU（0.625 vs 0.375 = +67%），降低升级的价格门槛                                                                      |
| Mem lim | 2Gi   | **核心卖点**：limit 是 Tiny 的 1.67x（1200Mi→2Gi）。2Gi 让 Chrome 几个 tab + code-server 可以舒服使用。从 1200Mi→2Gi 的体验提升是用户能直接感受到的——这就是"limit 武器"的体现 |
| CU/h    | 0.625 | 比 Tiny 贵 67%，但 memory burst 从 1.17x 跳到 2.0x——付费用户能明确感受到"钱花得值"                                                                     |


#### Medium — "舒适开发，不用想资源"（主力档）


| 参数      | 值     | 理由                                                                          |
| ------- | ----- | --------------------------------------------------------------------------- |
| CPU req | 1     | 1 整核，满足持续编译、测试、多进程并发                                                        |
| CPU lim | 1500m | 1.5x burst。medium 用户预期的是稳定开发体验而非极端峰值                                        |
| Mem req | 2Gi   | 2x Small request，为项目依赖、多标签 Chrome、大型 notebook 保留充足持续空间                      |
| Mem lim | 3Gi   | 1.5x burst。3Gi 可以同时跑 Chrome(3-4 tab) + code-server + 项目编译而不 OOM。占单节点仅 10.5% |
| CU/h    | 1.25  | 2x Small。"真正做开发"的基准档，适合 pro 用户日常使用                                          |


#### Large — "浏览器自动化 & 重度开发"（高阶档）


| 参数      | 值     | 理由                                                            |
| ------- | ----- | ------------------------------------------------------------- |
| CPU req | 2     | 多核编译、Playwright/Puppeteer 并行测试需要实打实的 CPU                      |
| CPU lim | 2500m | 1.25x burst。高档位 CPU 已充裕，不需要大比例 burst                          |
| Mem req | 4Gi   | 足够运行多个 Chrome 实例 + 中等规模项目 + 数据处理                              |
| Mem lim | 5Gi   | 1.25x burst。5Gi 是 Chromium 重度场景（10+ tab 或多实例）的安全线。占单节点约 17.5% |
| CU/h    | 2.5   | 2x Medium。适合 ultra 用户或需要浏览器自动化的 Agent 工作流                     |


#### XLarge — "最大规格，要什么给什么"（顶配档）


| 参数      | 值   | 理由                                                                                          |
| ------- | --- | ------------------------------------------------------------------------------------------- |
| CPU req | 4   | 覆盖并行编译、数据处理、ML 推理等 CPU 密集场景                                                                 |
| CPU lim | 5   | 1.25x burst。顶配档不需要靠 burst 比例取胜                                                              |
| Mem req | 8Gi | 足够跑大型项目 + 多浏览器实例 + 数据分析                                                                     |
| Mem lim | 9Gi | 1.125x，保守 burst。8Gi request 占单节点 28%，limit 9Gi 占 31.6%——单节点合理上限。集群总共 3 节点，需为其他 Pod 和系统服务留空间 |
| CU/h    | 5.0 | 2x Large。Enterprise 用户或重度 workload 专用                                                       |


### Limit burst 倍率设计曲线

```
         burst 倍率 (mem_limit / mem_request)
  2.0x │         * small
       │
  1.5x │              * medium
       │
  1.25x│                    * large
  1.17x│  * tiny
  1.125│                         * xlarge
       └─────────────────────────────────
         tiny  small  medium  large  xlarge
```

**中间高、两头低**——Small 的 burst 倍率最大（2.0x），是"升级奖励"。Tiny 和 XLarge 两端偏紧：Tiny 紧是因为要制造升级压力；XLarge 紧是因为已是最大规格，且要保护集群容量。

### 需改的文件

**Helm values（4 份，改法相同）：**

- [deploy/sandbox-runtime/values.yaml](deploy/sandbox-runtime/values.yaml)
- [deploy/sandbox-runtime/values-prod.yaml](deploy/sandbox-runtime/values-prod.yaml)
- [deploy/sandbox-runtime/values-demo.yaml](deploy/sandbox-runtime/values-demo.yaml)
- [deploy/sandbox-runtime/values-local.yaml](deploy/sandbox-runtime/values-local.yaml)

**Helm 模板（liveness 探针放宽）：**

- [deploy/sandbox-runtime/templates/sandbox-templates.yaml](deploy/sandbox-runtime/templates/sandbox-templates.yaml) — `livenessProbe.initialDelaySeconds` 15→60，加 `failureThreshold: 6`

**计量侧静态表（tiny request 变了）：**

- [treadstone/services/metering_helpers.py](treadstone/services/metering_helpers.py) L13 — `"aio-sandbox-tiny": {"memory_gib": Decimal("0.5")}` → `Decimal("1")`

**FakeK8sClient（测试用 stub）：**

- [treadstone/services/k8s_client.py](treadstone/services/k8s_client.py) L408 — tiny 的 `"memory": "512Mi"` → `"1Gi"`

## Part 3: 测试更新

- [tests/unit/test_metering_models.py](tests/unit/test_metering_models.py)
  - `TestCalculateCuRate`: 期望值从 `0.25, 0.5, 1, 2, 4` 改为 `0.375, 0.625, 1.25, 2.5, 5.0`
  - `test_ratio_is_1_to_2`: 删除这个断言（各档 CPU:Memory 不再强制 1:2 比例）；可改为验证 `calculate_cu_rate` 与 `CPU_WEIGHT * vcpu + MEMORY_WEIGHT * memory_gib` 一致
- [tests/api/test_usage_api.py](tests/api/test_usage_api.py) — `compute_unit_hours` 的期望值需按新公式重算
- [tests/unit/test_metering_tasks.py](tests/unit/test_metering_tasks.py) — 若有 CU 数值断言需更新

## Part 4: 文档同步

- [README.md](README.md) L129 — 更新 Built-in Templates 表（tiny memory → 1Gi 等）
- [web/public/docs/getting-started.md](web/public/docs/getting-started.md) L85 — 同上
- [docs/zh-CN/modules/05-metering-and-admin-ops.md](docs/zh-CN/modules/05-metering-and-admin-ops.md) L113 — CU 公式改为加权累加
- [docs/zh-CN/modules/05-metering-system-audit.md](docs/zh-CN/modules/05-metering-system-audit.md) L448 — 同上

## Part 5: Tier 月度额度

暂不调整（用户明确要求）。新公式下各档 CU 比旧公式高 25-50%，后续如需调整可通过新 Alembic migration 更新 `tier_template.compute_units_monthly`。

## 注意事项

- 本对话前面已对部分文件做了中间态修改（引入 `CU_MEMORY_GIB_DIVISOR`、部分 values 改动等），实施时需**覆盖**这些中间态到最终方案
- `metering_service.py` 和 `usage.py` 中的**三处内联 CU 计算**都需要改，不要遗漏
- Alembic migration 文件中的公式注释（如 `e1a2b3c4d5f6`）是历史记录，**不改**
