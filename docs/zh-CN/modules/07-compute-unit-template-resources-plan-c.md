# CU 加权公式与 Sandbox 模板资源方案 C

本文档描述 **Compute Unit（CU）计费公式** 从 `max(vCPU, memory/divisor)` 调整为 **加权累加**，以及 **五档 Sandbox 模板** 在 Kubernetes request/limit 上的统一设计（方案 C）。实施时需与 Helm `sandboxTemplates`、`metering_helpers.TEMPLATE_SPECS` 及控制面计量逻辑对齐。

**文档状态**：设计与实施清单；落地后以代码与模块 05（计量）为准同步更新。

---

## 1. 背景

- 集群中 `aio-sandbox-tiny` 的 warm pool Pod 曾因 **memory limit 过低（如 512Mi）** 与镜像内存底座不匹配而频繁 OOMKilled（稳态约 630–720Mi）。
- 旧公式 `max(vCPU, memory_GiB / divisor)` 使用 `max` 语义，与「CPU + 内存共同占用节点资源」的直觉不完全一致；改为 **加权累加** 更贴近调度与成本建模，且权重可调。
- 模板侧需同时解决 **计量依据（request）**、**调度保证** 与 **商业差异化（limit 曲线）**。

---

## 2. CU 公式：加权累加

### 2.1 定义

```
CU/hour = CPU_WEIGHT × vCPU_request + MEMORY_WEIGHT × memory_GiB_request
```

**建议初值**：`CPU_WEIGHT = 1.0`，`MEMORY_WEIGHT = 0.125`（即每 8 GiB request 折合 1 CU/h 的内存分量）。

### 2.2 与旧公式对照（各档 request 固定后）

| 模板 | vCPU req | Mem req (GiB) | 新 CU/h（示例） | 旧公式典型值（参考） |
|------|-----------|----------------|-----------------|--------------------------------|
| tiny | 0.25 | 1 | **0.375** | 0.25（若仅按 CPU） |
| small | 0.5 | 1 | **0.625** | 0.5 |
| medium | 1 | 2 | **1.25** | 1.0 |
| large | 2 | 4 | **2.5** | 2.0 |
| xlarge | 4 | 8 | **5.0** | 4.0 |

计算示例：`tiny = 1.0×0.25 + 0.125×1 = 0.375`。

### 2.3 代码对齐要点

- **单一来源**：`calculate_cu_rate`（如 `metering_helpers.py`）应实现加权公式；`metering_service`、`usage` 等处的 **内联 CU 聚合** 须与之一致，避免分叉。
- **模板静态表**：`TEMPLATE_SPECS` 中各 tier 的 `memory_gib` 须与 **K8s memory request** 一致（例如 tiny 从 0.5 GiB 调整为 1 GiB 时，表与 Helm 同时改）。
- **历史迁移**：Alembic 历史文件中的公式注释可保留为历史记录，不必为叙述一致性去改旧 migration 正文。

---

## 3. Sandbox 模板方案 C（五档）

### 3.1 前提与约束

- **集群参考**：例如 3 节点 × 16 CPU × 约 28.5 GiB allocatable（实际以目标集群为准）。
- **镜像特性**：内存底座较高（多进程：supervisord、nginx、code-server、Jupyter、Chromium、VNC 等），空闲时 **CPU 占用可很低、内存占用可达数百 MiB**。
- **设计原则**：
  - **Request** = 计量与调度基线，取「典型持续负载」。
  - **Limit** = 硬上限，用作 **档位差异化**：低档位 limit 偏紧以引导升级；中档位 limit 相对慷慨以体现付费价值。
  - **内存**：各档 **memory request 至少 1Gi**，避免与镜像底座冲突。
  - **大规格**：xlarge 的 limit 不宜占满单节点，需为系统与其他 Pod 留余量。

### 3.2 总表（须与 Helm / `TEMPLATE_SPECS` 对齐）

| Tier | CPU req | CPU lim | Memory req | Memory lim | 内存 burst（lim/req） | CU/h（新公式） |
|------|---------|---------|------------|------------|------------------------|----------------|
| tiny | 250m | 500m | 1Gi | 1200Mi | ≈1.17× | 0.375 |
| small | 500m | 1000m | 1Gi | 2Gi | 2.0× | 0.625 |
| medium | 1 | 1500m | 2Gi | 3Gi | 1.5× | 1.25 |
| large | 2 | 2500m | 4Gi | 5Gi | 1.25× | 2.5 |
| xlarge | 4 | 5 | 8Gi | 9Gi | ≈1.125× | 5.0 |

### 3.3 分档摘要

| 档位 | 定位 | 要点 |
|------|------|------|
| **tiny** | 入口档 | Mem request 1Gi 保稳；mem limit 刻意偏紧，促使用户感知「能用但局促」并升级。 |
| **small** | 性价比甜蜜点 | 与 tiny **同 mem request**；差价主要来自 CPU；**mem limit 提升至 2Gi**， burst 倍率最高，体现「升级即质变」。 |
| **medium** | 主力开发 | 1C / 2Gi request，limit 适度；适合日常开发与多标签浏览器场景。 |
| **large** | 重度 / 浏览器自动化 | 2C / 4Gi request；适合并行编译、多 Chromium 实例等。 |
| **xlarge** | 顶配 | 4C / 8Gi request；limit 保守（如 9Gi），避免占满单节点。 |

### 3.4 Limit burst 倍率曲线（概念）

中间档位（small）burst 比例最高，作为「升级奖励」；tiny 与 xlarge 两端相对收紧：tiny 为商业引导，xlarge 为集群容量保护。

---

## 4. 部署与探针

- **Helm values**：`deploy/sandbox-runtime/values*.yaml` 中 `sandboxTemplates` 资源需与上表一致（多环境文件同步修改）。
- **模板清单**：`deploy/sandbox-runtime/templates/sandbox-templates.yaml` 等中 **liveness** 建议放宽（例如 `initialDelaySeconds` 提升至约 60、`failureThreshold` 约 6），避免慢启动镜像被误杀（具体以集群观测为准）。
- **控制面测试桩**：如 `FakeK8sClient` 中 tiny 的 memory 应与 values 一致（例如 512Mi → 1Gi）。

---

## 5. Tier 月度额度

**当前决策**：月度 **CU·h 套餐额度** 可不与公式改动强制联动；若产品后续按新费率调整套餐，可通过数据迁移或更新 `tier_template.compute_units_monthly` 等方式单独处理。

---

## 6. 实施检查清单（跨仓库文件）

| 区域 | 内容 |
|------|------|
| 计量核心 | `metering_helpers`：权重常量、`calculate_cu_rate`、`TEMPLATE_SPECS`（含 tiny memory_gib） |
| 聚合与 API | `metering_service`、`usage`：内联 CU 与核心公式一致 |
| 部署 | 各环境 `values*.yaml`、sandbox 模板 YAML（探针） |
| 测试 | `test_metering_models`、`test_usage_api`、`test_metering_tasks` 等 CU 期望值 |
| 用户可见文档 | README、getting-started、模块 05 等：公式与模板表同步 |

---

## 7. 注意事项

- 实施时若存在「中间态」改动，应以 **本文档与上表** 为最终对齐目标一次性收束。
- 公式、模板与 **request** 严格一致，避免计量与调度漂移。
