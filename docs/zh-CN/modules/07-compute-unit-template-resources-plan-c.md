---
name: CU formula, template resources, and tier policy
overview: 基于新加坡 ACK 小集群、AIO sandbox 的真实内存底座，以及当前 free/pro/ultra/custom 套餐现状，重新定义 Compute Unit 公式、模板 request/limit、Tier 月度额度与模板白名单。此版本取代原文档“只改公式和模板、不调整 Tier”的结论。
todos:
  - id: formula
    content: "将 `CU_MEMORY_GIB_DIVISOR` 改为显式权重常量：`CPU_WEIGHT = 0.5`、`MEMORY_WEIGHT = 0.125`，统一替换 `metering_helpers.py`、`metering_service.py`、`usage.py` 中的 CU 公式。"
    status: pending
  - id: template-specs
    content: "将内置模板 request/limit 调整为本文表格；`tiny` request 固定升到 `1Gi`；同步 Helm values、`TEMPLATE_SPECS` 与 `FakeK8sClient`。"
    status: pending
  - id: tier-defaults
    content: "新增 Alembic migration，更新 `tier_template` 默认额度、并发、时长、grace period 与 `allowed_templates`。"
    status: pending
  - id: xlarge-gating
    content: "默认将 `aio-sandbox-xlarge` 仅开放给 `custom`；若后续集群 allocatable memory 与真实负载证明足够，再评估是否下放给 `ultra`。"
    status: pending
  - id: docs-sync
    content: "同步 README、模块 02、模块 05、公开文档中的模板规格与 Tier 描述，移除已过时的旧额度与旧公式。"
    status: pending
isProject: false
---

# Compute Unit、模板资源与 Tier 设计（方案 C 修订版）

## 1. 结论摘要

这份文档直接回答四个核心问题。

### 1.1 Compute Unit 公式

保留“**加权累加**”方向，但**不采用**原文的 `CPU_WEIGHT = 1.0`、`MEMORY_WEIGHT = 0.125`。

建议改为：

```text
CU / hour = 0.5 * vCPU_request + 0.125 * memory_GiB_request
```

原因：

- 这仍然是连续、可调、可解释的公式，比 `max(...)` 更合理。
- `0.5 : 0.125` 的相对权重等价于 **1 vCPU 对应 4 GiB 内存**，更接近主流开发/托管环境的资源梯度，也更适合你计划中的 ACK 节点配置。
- 原文的 `1.0 : 0.125` 等价于 **1 vCPU 对应 8 GiB 内存**，会把内存定得过便宜；对一个总内存不打算超过 `256Gi` 的小集群来说，这不利于成本控制。

### 1.2 Template 的 request / limit 比例

原文把 `tiny` request 升到 `1Gi` 是正确的，但整体模板表仍然偏向“CPU 便宜、内存更便宜”的思路，且 `small` 的 `1Gi request` 仍然偏低。

建议新的 request/limit 阶梯如下：

| Template | CPU Request | CPU Limit | Memory Request | Memory Limit | CU/h |
| --- | --- | --- | --- | --- | --- |
| `aio-sandbox-tiny` | `250m` | `500m` | `1Gi` | `1536Mi` | `0.25` |
| `aio-sandbox-small` | `500m` | `1000m` | `2Gi` | `3Gi` | `0.5` |
| `aio-sandbox-medium` | `1` | `2` | `4Gi` | `6Gi` | `1.0` |
| `aio-sandbox-large` | `2` | `3` | `8Gi` | `10Gi` | `2.0` |
| `aio-sandbox-xlarge` | `4` | `5` | `16Gi` | `20Gi` | `4.0` |

总体原则：

- **request 用于计量与调度**，应反映稳态真实占用，不是“勉强启动”值。
- **limit 用于 UX 与短时突发**，但对内存不宜给过大倍率，否则在小集群上容易把风险留给节点级 OOM。
- 公开 Tier 下，memory limit/request 最好控制在 **1.25x 到 1.5x**，不要再走 2x 内存 overcommit。

### 1.3 Tier 月度额度

建议把当前默认额度从：

- `free = 20`
- `pro = 120`
- `ultra = 400`
- `custom = 1000`

调整为：

- `free = 20`
- `pro = 160`
- `ultra = 480`
- `custom = 1600`（管理员默认基线，不是对外承诺价）

这不是“越高越好”，而是为了让新模板表下各 Tier 的**等效模板小时数**更平衡。

### 1.4 每个 Tier 允许使用哪些模板

建议明确为：

| Tier | Allowed Templates |
| --- | --- |
| `free` | `aio-sandbox-tiny` |
| `pro` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium` |
| `ultra` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium`, `aio-sandbox-large` |
| `custom` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium`, `aio-sandbox-large`, `aio-sandbox-xlarge` |

结论上，**`xlarge` 先不要开放给 `ultra`**。在你当前“单人项目 + 小集群 + 总内存敏感”的现实前提下，把 `xlarge` 作为 `custom` / 人工审批资源更稳。

## 2. 审计输入与边界条件

这次修订不再沿用原文“香港区 3 节点固定集群”的默认前提，而采用你给出的新条件：

- 项目规模：单人项目
- 部署位置：阿里云新加坡 ACK
- 节点形态：可能是 `2 x 32C / 64Gi`，也可能转向更适合该镜像的 `1:4` 内存型节点
- 集群总体量：预计不会超过 `256Gi` 总内存

另外，我核对了现网 ACK 的实际使用情况：

- `kubectl top pods -A` 在 `2026-03-31` 看到 `aio-sandbox-tiny` warm pool 稳态约 `634Mi` 到 `638Mi`
- 当前香港集群节点 allocatable 大约是 `15.89 vCPU / 27.9 GiB` 每节点

这说明两件事：

1. `tiny` 的 memory request 继续维持 `512Mi` 已经没有现实依据。
2. 你当前这套 AIO sandbox 镜像是**明显内存底座偏高**的环境，不能套用轻量容器平台的资源认知。

## 3. 对原方案 C 的审计结论

### 3.1 原方案里值得保留的部分

- 把 CU 从 `max(vCPU, memory/2)` 改成加权累加，这个方向正确。
- 把 `tiny` request 从 `512Mi` 提到至少 `1Gi`，这个结论正确，而且有现网数据支撑。
- 把 limit 当作不同模板的体验差异化手段，这个产品思路可以保留。

### 3.2 原方案里不应继续保留的部分

### A. `CPU_WEIGHT = 1.0`、`MEMORY_WEIGHT = 0.125` 不合理

这个组合等价于：

- `1 vCPU = 8 GiB memory`

这会显著低估内存成本。对总内存受限的小集群，这种权重会把大部分成本压力留给“模板白名单”和“人工运营”，而不是直接反映在计量模型里。

### B. `small` 仍然只给 `1Gi request` 不合理

如果 `tiny` 已经确认需要 `1Gi request` 才稳定，那么 `small` 继续给 `1Gi request` 的意义就很弱：

- 它会让 `small` 的稳态调度承诺与 `tiny` 几乎一致
- 却试图用更高 limit 提供体验差异
- 这会抬高集群 overcommit 风险，并让 `request` 失去“计量与调度锚点”的意义

### C. “Tier 暂不调整”这个结论不再成立

你已经明确希望调整 Tier，而且从设计上也确实应该调整。原因是：

- 公式变了
- 模板 request 变了
- 可开放模板集合要重新定义

这三个量一起变化时，Tier 额度不应该保持“碰巧沿用旧值”。

### D. 缺少明确的模板开放策略

原文没有明确写出：

- 哪些模板是 public self-serve
- 哪些模板需要人工放行
- 在 `2 x 32C / 64Gi` 这种小集群上，`xlarge` 是否真的适合作为公开规格

这部分必须补齐，否则实现层会默认把“有模板定义”误解成“应该对相应 Tier 开放”。

## 4. 市场参考与设计取向

这次修订参考了几类公开方案，重点不是照抄，而是提炼出适合 Treadstone 当前阶段的共性。

### 4.1 市场上常见的两种计费方式

#### 方式 A：离散机器规格 + 套餐内含小时数

代表：

- [GitHub Codespaces billing](https://docs.github.com/billing/managing-billing-for-github-codespaces/about-billing-for-github-codespaces)
- [GitHub Codespaces machine types](https://docs.github.com/en/codespaces/customizing-your-codespace/changing-the-machine-type-for-your-codespace)

特点：

- 直接给用户几个固定规格
- 套餐限制可用的机器类型
- 内含一定的月度时长

这和 Treadstone 当前的“模板 + Tier + allowed_templates”模型最接近。

### 4.2 方式 B：CPU / Memory 拆开计价

代表：

- [Railway Pricing](https://railway.com/pricing)
- [Daytona Pricing](https://www.daytona.io/pricing)

特点：

- CPU 与内存分别定价
- 更灵活，但也更复杂
- 适合大平台或面向较成熟用户的精细计费

对于当前阶段的 Treadstone，这种方式**可以借鉴权重，不建议直接照搬到产品面**。你现在更需要的是“少量模板 + 明确白名单 + 稳定可控的月度额度”，而不是做成一个云厂商计费系统。

### 4.3 资源比例参考

- GitHub Codespaces 的机器规格基本体现了开发环境常见的 `1:4` CPU:Memory 梯度
- Daytona 的托管 sandbox 公开规格上限也是“CPU 与内存同时受控”
- [Alibaba Cloud Hologres 的 CU 概念](https://www.alibabacloud.com/help/en/hologres/product-overview/instance-billing) 也采用接近 `1 core + 4 GiB` 的资源锚点

因此，对 Treadstone 来说，更合理的方向是：

- 仍用模板制
- 采用 **1:4 的 CPU:Memory 相对权重**
- 让 Tier 控制“能用哪些模板”和“一个月可跑多少小时”

## 5. Compute Unit 公式设计

### 5.1 推荐公式

```text
CU / hour = 0.5 * vCPU_request + 0.125 * memory_GiB_request
```

解释方式：

- 一个 **`1 vCPU + 4 GiB` 的平衡型 request**，记作 **`1 CU / hour`**
- 公式基于 request，而不是 limit
- CPU 与内存都参与成本表达，不再出现 `max(...)` 的“只取一边”的失真

### 5.2 为什么不继续使用 `max(...)`

旧公式：

```text
CU / hour = max(vCPU_request, memory_GiB_request / 2)
```

问题：

- 它只会让 CPU 或内存其中一边生效，另一边“免费”
- 对双资源都真实消耗的 sandbox 不合理
- 当模板资源梯度变化时，价格跳点不自然

### 5.3 为什么不采用原文的 `1.0 + 0.125`

原文公式：

```text
CU / hour = 1.0 * vCPU_request + 0.125 * memory_GiB_request
```

问题：

- 内存权重过低
- 对总内存受限的小集群不友好
- 会鼓励更高 memory request，却没有在月度额度里同步体现相应稀缺性

### 5.4 新公式下的模板费率

按本文推荐模板 request 计算：

| Template | vCPU Request | Memory Request | CU/h |
| --- | --- | --- | --- |
| `aio-sandbox-tiny` | `0.25` | `1Gi` | `0.25` |
| `aio-sandbox-small` | `0.5` | `2Gi` | `0.5` |
| `aio-sandbox-medium` | `1` | `4Gi` | `1.0` |
| `aio-sandbox-large` | `2` | `8Gi` | `2.0` |
| `aio-sandbox-xlarge` | `4` | `16Gi` | `4.0` |

这个梯度有三个好处：

- 好记：`0.25 / 0.5 / 1 / 2 / 4`
- 对用户透明：模板扩大一档，CU 也基本扩大一档
- 对运营简单：Tier 月度额度可以直接换算成“某规格可跑多少小时”

## 6. 模板资源设计

### 6.1 设计原则

### 原则 1：request 是调度与计量锚点

`request` 必须反映这类 sandbox 的**正常使用预期**，而不是“勉强启动”。

### 原则 2：limit 负责突发，不负责长期超卖

CPU 可以比 request 放得更松一些；memory 要保守一些。

### 原则 3：公开模板优先控制 memory 风险

对你的集群来说，真正容易先撞到上限的更可能是内存，不是 CPU。

### 原则 4：`xlarge` 是稀缺资源

无论模板定义是否存在，早期都不应该默认把 `xlarge` 当作所有付费用户都能随手点的规格。

### 6.2 推荐模板表

| Template | 主要定位 | CPU Request | CPU Limit | Memory Request | Memory Limit | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| `aio-sandbox-tiny` | 体验、脚本、轻量 Agent 任务 | `250m` | `500m` | `1Gi` | `1536Mi` | 保证镜像底座稳定；limit 只给有限余量 |
| `aio-sandbox-small` | 轻量开发、少量浏览器标签 | `500m` | `1000m` | `2Gi` | `3Gi` | 真正和 `tiny` 拉开差距的入口付费规格 |
| `aio-sandbox-medium` | 主力开发规格 | `1` | `2` | `4Gi` | `6Gi` | 推荐作为大多数日常开发的默认付费模板 |
| `aio-sandbox-large` | 浏览器自动化、较重编译 | `2` | `3` | `8Gi` | `10Gi` | 高阶规格，但仍适合公开开放给顶级自助 Tier |
| `aio-sandbox-xlarge` | 多浏览器实例、重型数据处理 | `4` | `5` | `16Gi` | `20Gi` | 默认仅开放给 `custom`，不做自助规格 |

### 6.3 比例解释

### CPU burst

- `tiny` / `small` / `medium`: `2x`
- `large`: `1.5x`
- `xlarge`: `1.25x`

CPU burst 可以适当宽松，因为 CPU 抢占比 memory overcommit 更可控。

### Memory burst

- `tiny`: `1.5x`
- `small`: `1.5x`
- `medium`: `1.5x`
- `large`: `1.25x`
- `xlarge`: `1.25x`

大规格内存必须收紧。否则在 `2 x 32C / 64Gi` 这类起步集群上，一两个大规格峰值就会显著抬高节点压力。

### 6.4 为什么不采用原文的 `small = 1Gi request`

因为这会带来两个问题：

- `small` 与 `tiny` 的调度承诺几乎重合
- 你会在业务上卖出“明显更舒服”的体验，但在集群层面却没给它相应 request

这对小集群是反模式。

## 7. Tier 设计

### 7.1 推荐默认 Tier

| Tier | Compute Units / 月 | Storage 容量 | 并发上限 | 最长时长 | Allowed Templates | Grace Period |
| --- | --- | --- | --- | --- | --- | --- |
| `free` | `20` | `0 GiB` | `1` | `7200s` | `aio-sandbox-tiny` | `900s` |
| `pro` | `160` | `20 GiB` | `3` | `86400s` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium` | `7200s` |
| `ultra` | `480` | `100 GiB` | `8` | `259200s` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium`, `aio-sandbox-large` | `21600s` |
| `custom` | `1600` | `250 GiB` | `20` | `604800s` | 全部模板，含 `aio-sandbox-xlarge` | `86400s` |

### 7.2 额度换算

按本文 CU 表，等效模板小时数如下：

| Tier | Tiny Hours | Small Hours | Medium Hours | Large Hours | XLarge Hours |
| --- | --- | --- | --- | --- | --- |
| `free` | `80` | - | - | - | - |
| `pro` | `640` | `320` | `160` | - | - |
| `ultra` | `1920` | `960` | `480` | `240` | - |
| `custom` | `6400` | `3200` | `1600` | `800` | `400` |

这里的重点不是让用户去精确换算，而是验证：

- `free` 足够做试用，但不会支撑长期重度使用
- `pro` 足够支撑单人开发者的主力使用
- `ultra` 足够支撑浏览器自动化和重度开发
- `custom` 才承接真正昂贵的大规格

### 7.3 为什么 `free` 仍然保留 `20`

`free` 额度可以保留 `20`，但前提是：

- 只开放 `tiny`
- 并发严格为 `1`
- 不给持久存储

这样它的运营风险主要是“试用流量”，而不是“被拿来跑持续任务”。

### 7.4 为什么 `pro` 调到 `160`

`pro` 需要成为真正的甜蜜点。

如果维持 `120`：

- 在新模板表下，只相当于 `120` 小时 `medium`
- 对一个主力开发套餐略显紧张

调到 `160` 后：

- 仍然明显低于 `ultra`
- 但能覆盖更完整的个人开发场景
- 与市场上“中档开发者套餐含较明确月度额度”的心智更接近

### 7.5 为什么 `ultra` 调到 `480`

`ultra` 的价值不应该只是“比 `pro` 多一点”，而应该明确支持：

- 较长时间的 `large`
- 更高的并发
- 更长的运行时长

`480` 让 `ultra` 在 `large` 上有 `240` 小时，才像一个高阶开发 / 自动化 Tier，而不是“高一点点的 pro”。

### 7.6 `custom` 的定位

`custom` 不应该被理解成对外公布的标准套餐，而是：

- 管理员人工分配的默认基线
- 用于 `xlarge`
- 用于特殊客户或内部用户

因此 `1600` 是**默认 seed**，不是最终承诺值；管理员可以按用户实际情况 override。

## 8. 模板开放策略

### 8.1 早期阶段的明确策略

### 公开自助模板

- `tiny`
- `small`
- `medium`
- `large`

### 人工控制模板

- `xlarge`

### 8.2 为什么 `xlarge` 先不开放给 `ultra`

原因不是产品能力不够，而是运营现实：

- 你是单人项目
- 集群不会很大
- 总内存上限敏感
- 大规格的坏体验和成本波动都更明显

在这种阶段，把 `xlarge` 留给 `custom` 有三个好处：

- 降低误用和滥用风险
- 保留一档明确的人工审批资源
- 等有真实使用数据后再决定是否下放给 `ultra`

### 8.3 何时考虑把 `xlarge` 下放给 `ultra`

建议满足以下条件后再评估：

- 集群 allocatable memory 稳定达到 `>= 192Gi`
- 连续 30 天，工作时段 `p95` memory headroom 仍然 `> 30%`
- 已有 `large` 用户明显触及上限，而不是少量偶发请求

在这之前，不建议将其作为自助规格。

## 9. 与节点形态的匹配

### 9.1 推荐优先选择 `1:4` 类型节点

对当前 AIO sandbox 镜像来说，更合适的节点不是 CPU 偏多型，而是 memory 更充裕的节点。

原因：

- idle 底座已经接近 `0.65Gi`
- 浏览器、VS Code、Jupyter 都明显吃内存
- 小集群中更容易先被 memory 卡住

所以，在“`2 x 32C / 64Gi`”和“`1:4` 内存型节点”之间，如果预算允许，**优先选 `1:4`**。

### 9.2 如果起步就是 `2 x 32C / 64Gi`

这仍然能跑，但需要遵守两个运营约束：

- `xlarge` 不开放给 `ultra`
- `tiny` 之外的 warm pool 保持关闭

这套文档中的 Tier 与模板表已经按这个约束设计，不需要额外再打折扣。

## 10. 实施影响

如果按本文落地，至少要同步以下地方。

### 10.1 公式

- `treadstone/services/metering_helpers.py`
- `treadstone/services/metering_service.py`
- `treadstone/api/usage.py`

将：

```text
max(vCPU_request, memory_GiB_request / 2)
```

改为：

```text
0.5 * vCPU_request + 0.125 * memory_GiB_request
```

### 10.2 模板静态表与 Helm values

- `deploy/sandbox-runtime/values.yaml`
- `deploy/sandbox-runtime/values-local.yaml`
- `deploy/sandbox-runtime/values-demo.yaml`
- `deploy/sandbox-runtime/values-prod.yaml`
- `treadstone/services/metering_helpers.py`
- `treadstone/services/k8s_client.py`

### 10.3 Tier 默认值

新增 migration，更新：

- `compute_units_monthly`
- `storage_capacity_gib`
- `max_concurrent_running`
- `max_sandbox_duration_seconds`
- `allowed_templates`
- `grace_period_seconds`

### 10.4 文档同步

需要同步至少：

- `README.md`
- `docs/zh-CN/modules/02-sandbox-lifecycle-and-templates.md`
- `docs/zh-CN/modules/05-metering-and-admin-ops.md`
- `docs/zh-CN/modules/05-metering-system-audit.md`
- `web/public/docs/getting-started.md`

## 11. 最终建议

如果只保留一句话作为执行结论，就是：

**保留加权累加；把相对权重改成 `1 vCPU : 4 GiB`；把模板 request 升到真正可调度的梯度；把 `xlarge` 先收口到 `custom`；把默认 Tier 调整为 `free 20 / pro 160 / ultra 480 / custom 1600`。**

这套方案比原方案更适合你当前的真实约束：

- 更适合小集群
- 更适合内存敏感的 AIO sandbox 镜像
- 更适合单人项目的运营复杂度
- 也更容易在未来逐步放开，而不是先放太宽再回收
