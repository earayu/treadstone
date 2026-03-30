---
name: CU formula, template resources, and tier policy
overview: 基于新加坡 ACS 冷启动、未来 ACK 增长期，以及 AIO sandbox 的真实内存底座，重新定义 Compute Unit 公式、模板 request/limit、Tier 月度额度、模板白名单、上线期/增长期资源策略与建议收费标准。此版本取代原文档“只改公式和模板、不调整 Tier”的结论。
todos:
  - id: formula
    content: "将 CU 计算改为基于 `effective billed spec`：ACS 读取 `alibabacloud.com/pod-use-spec`（或显式 required spec），ACK 读取 pod request；统一替换 `metering_helpers.py`、`metering_service.py`、`usage.py`。"
    status: pending
  - id: template-specs
    content: "将内置模板拆成 ACS / ACK 双配置：ACS 使用 `request = limit` 且命中官方支持规格；ACK 保持相同 request，再恢复有限 burst limit。"
    status: pending
  - id: tier-defaults
    content: "新增 Alembic migration，将默认 seed 调整为 ACS 启动期额度；ACK 增长期额度作为后续升级迁移。"
    status: pending
  - id: rollout-phases
    content: "补充 ACS 启动期 / ACK 增长期 / ACK+ACS 混合期三种运营阶段，明确模板开放、warm pool、并发和时长策略。"
    status: pending
  - id: welcome-bonus
    content: "关闭当前 `50 CU / 90 天` 自动 welcome bonus，改成按活动显式发放 ComputeGrant。"
    status: pending
  - id: pricing-policy
    content: "补充 ACS 冷启动期免费运营策略，以及未来付费上线后的建议公开售价与 `custom` 报价下限。"
    status: pending
  - id: storage-strategy
    content: "补充 ACS / ACK 下 persistent sandbox 的存储策略；ACS 下 direct path 不再自动按代码 `2x request` 推导 limit；评估 cloud disk 与 NAS 共享用户工作区两种方案。"
    status: pending
  - id: docs-sync
    content: "同步 README、模块 02、模块 05、公开文档中的模板规格、Tier 描述与平台假设，移除旧额度、旧公式与旧 welcome bonus 口径。"
    status: pending
isProject: false
---

# Compute Unit、模板资源与 Tier 设计（方案 C，ACS 启动版）

## 1. 结论摘要

### 1.1 平台选择

如果你接下来是 **SaaS 冷启动 + 免费给用户用 + 项目成败不确定**，应当优先选择 **ACS**，而不是一开始就买 ACK 节点。

原因：

- ACS **没有集群管理费**，按 Pod 的 vCPU 与内存 **按秒计费**
- 失败时的固定成本最低
- 成功后可以升级到 **ACK Pro + ACS virtual node**，不需要推翻模板与套餐体系

官方依据：

- [ACS billing rules](https://www.alibabacloud.com/help/en/cs/product-overview/product-billing-rules)
- [Use ACS computing power in ACK Pro clusters](https://www.alibabacloud.com/help/en/cs/user-guide/access-acs-computing-power-in-an-ack-cluster)

### 1.2 ACS 下模板必须改

原文档里 ACK 风格的 `limit > request` 在 ACS 上不再适合作为默认模板策略。

不是因为 ACS 完全“不接受”不同的 request / limit，而是因为：

- ACS 会按 **`max(sum(requests), sum(limits))`** 做规格规整并计费
- 如果规格不在支持表里，还会**向上规整到最近支持规格**
- 也就是说，在 ACS 上把 `limit` 设得更大，不会让你“省 request”，只会让**计费规格和容量保底一起变大**

官方依据：

- [ACS pod overview](https://www.alibabacloud.com/help/en/cs/user-guide/acs-pod-instance-overview)

因此，**ACS 启动期的默认模板应改为 `request = limit`**，并且必须命中官方支持的精确规格。

### 1.3 ACK 升级后模板怎么调

未来升级到 ACK 后，不需要改模板的 **request 梯度**，只需要：

- 保留 ACS 阶段已经验证过的 request
- 在 ACK 上恢复有限的 `limit > request`
- 让 CPU / memory 有适度 burst，但不重新改 Tier 心智

换句话说：

- **ACS 决定 request**
- **ACK 决定 limit**

### 1.4 CU 算法要不要改

**要小改，但不是推翻。**

保留这条核心定义：

```text
1 CU / hour = 1 vCPU + 4 GiB effective spec
```

统一公式仍然可以写成：

```text
CU / hour = 0.5 * effective_vCPU + 0.125 * effective_memory_GiB
```

但这里的 `effective spec` 要明确区分平台：

- **ACS**：取 ACS 规整后的实际计费规格，也就是 `alibabacloud.com/pod-use-spec`
- **ACK**：取 pod 的 request

这一步是必须补充的，否则在 ACS 上可能出现“声明规格”和“实际计费规格”不一致，导致计量低估。

### 1.5 Tier 额度也要改

此前文档里给出的 `free 20 / pro 160 / ultra 480 / custom 1600`，更适合作为 **ACK 增长期目标值**，不适合作为 **ACS 冷启动默认 seed**。

对你现在的 ACS 冷启动场景，我建议默认 seed 调整为：

| Tier | Compute Units / 月 | Allowed Templates |
| --- | --- | --- |
| `free` | `10` | `aio-sandbox-tiny` |
| `pro` | `80` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium` |
| `ultra` | `240` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium` |
| `custom` | `800` | 全部模板，含 `aio-sandbox-large`, `aio-sandbox-xlarge` |

而在未来 ACK 增长期，再切换到：

| Tier | Compute Units / 月 | Allowed Templates |
| --- | --- | --- |
| `free` | `20` | `aio-sandbox-tiny` |
| `pro` | `160` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium` |
| `ultra` | `480` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium`, `aio-sandbox-large` |
| `custom` | `1600` | 全部模板，含 `aio-sandbox-xlarge` |

### 1.6 收费标准怎么定

如果你当前阶段是免费运营，那么**用户实际收费可以是 0**，但产品内部仍然要有“标准价格带”，否则将来很难切换到收费。

建议分两层表达：

| 阶段 | `free` | `pro` | `ultra` | `custom` |
| --- | --- | --- | --- | --- |
| 启动期促销价 | `¥0` | `¥0` | `¥0` | 人工报价 |
| 未来公开标价 | `¥0 / 月` | `¥99 / 月` | `¥299 / 月` | `¥999 / 月` 起 |

其中：

- 启动期的 `pro` / `ultra` 免费，只是促销策略，不是长期价格承诺
- `custom` 不建议做成自助套餐

## 2. 输入条件与官方约束

### 2.1 你的实际边界条件

- 项目规模：单人项目
- 部署区域：新加坡
- 当前阶段：SaaS 冷启动
- 商业策略：先免费给用户用，甚至可能直接送 `pro` / `ultra`
- 风险偏好：项目可能失败，因此固定成本应尽量低

### 2.2 本地现网 AIO sandbox 的真实底座

`2026-03-31` 本地集群 `kubectl top pods -A` 看到 `aio-sandbox-tiny` warm pool 稳态大约在 `634Mi` 到 `638Mi`。

这说明：

1. `tiny` 的 memory request 继续用 `512Mi` 没有现实依据。
2. 当前 AIO sandbox 明显不是“超轻量容器”，它有比较高的内存底座。

### 2.3 ACS 的关键官方事实

#### 计费

以 **Hong Kong (China) and outside China** 的 **general-purpose / default** 为例，官方价格是：

- vCPU：`USD 0.013716 / vCPU-hour`
- 内存：`USD 0.0069 / GiB-hour`

也就是：

- ACS **不是按固定 1:2 或 1:4 套餐收费**
- ACS 是 **CPU 和内存分别计费**
- 只是 pod 规格必须落在官方支持表里，超出后会向上规整

来源：

- [ACS billing rules](https://www.alibabacloud.com/help/en/cs/product-overview/product-billing-rules)

#### 规格规整

ACS 会：

1. 取 `.resources.requests` 与 `.resources.limits` 的累计最大值
2. 向上规整到最近支持规格
3. 在 pod 上写入 `alibabacloud.com/pod-use-spec`

例如：

- `2 vCPU + 3.5 GiB` 会被规整成 `2 vCPU + 4 GiB`

来源：

- [ACS pod overview](https://www.alibabacloud.com/help/en/cs/user-guide/acs-pod-instance-overview)

#### 常用 CPU 规格的 memory 范围

以 **general-purpose** 为例，官方支持：

- `0.25 vCPU`：`0.5 / 1 / 2 GiB`
- `0.5 vCPU`：`1` 到 `4 GiB`
- `1 vCPU`：`1` 到 `8 GiB`
- `2 vCPU`：`2` 到 `16 GiB`
- `4 vCPU`：`4` 到 `32 GiB`

这意味着本文使用的 `0.25/1`, `0.5/2`, `1/4`, `2/8`, `4/16` 都是**原生支持规格**，不会被向上规整。

#### 平台限制

ACS 官方限制包括：

- 不支持 `DaemonSet`
- 不支持 `HostPath`
- 不支持 `HostNetwork`
- 不支持 privileged container
- 不支持 `NodePort` Service

来源：

- [ACS overview](https://www.alibabacloud.com/help/en/cs/product-overview/product-introduction)
- [ACS pod overview](https://www.alibabacloud.com/help/en/cs/user-guide/acs-pod-instance-overview)

### 2.4 ACK 与 ACS 的升级路径

ACK Pro 可以通过 virtual node 接入 ACS 算力。因此你的推荐演进顺序是：

1. **现在：ACS**
2. **后续：ACK Pro + 少量固定 ECS 节点**
3. **再后续：ACK Pro + ECS 节点池 + ACS 弹性峰值**

来源：

- [Use ACS computing power in ACK Pro clusters](https://www.alibabacloud.com/help/en/cs/user-guide/access-acs-computing-power-in-an-ack-cluster)

## 3. 平台策略

### 3.1 阶段 A：ACS 启动期

目标：

- 最低固定成本
- 最小化失败损失
- 保留真实用户试用数据

策略：

- 默认只用 **ACS general-purpose / default**
- 模板用 `request = limit`
- 只使用命中官方支持表的精确规格
- 不做公开 `large` / `xlarge`
- warm pool 默认关闭

### 3.2 阶段 B：ACK 增长期

当满足以下任一条件时，开始评估迁移到 ACK：

- 连续 30 天有稳定活跃用户
- 工作时段 `p95` 并发 sandbox 明显大于 5
- ACS 月账单已经持续接近“买两台 16C / 64Gi 通用型节点”的成本
- 你需要更稳定的 warm pool 和 burst 体验

进入 ACK 后：

- ECS 节点池承接稳态流量
- 可重新启用 `limit > request`
- `large` 再开放给 `ultra`

### 3.3 阶段 C：ACK + ACS 混合期

最理想的长期形态不是“ACS 完全换成 ACK”，而是：

- 稳态主流量在 ACK 节点池
- 峰值或不确定流量走 ACS virtual node

这能同时保留：

- ACK 的成本可预测性
- ACS 的弹性与免预留能力

### 3.4 什么时候纯 ACS 更省，什么时候 ACK + ACS 更省

这件事不能一概而论。

#### 纯 ACS 更省的情况

- 固定前端 / 后端 Pod 规模还很小
- warm pod 只有 `0~1` 个，或者并不是 24x7 常驻
- 总体常驻资源还不到一台小规格 ECS 的一半
- 你更在意“如果项目失败，我每个月最多亏多少”

在这个阶段，纯 ACS 通常更划算，因为：

- ACS 没有集群管理费
- 不需要预留 ECS worker
- 失败时损失最小

#### ACK + ACS 更省的情况

- 前端、后端、队列、运营组件已经形成**稳定 24x7 基线**
- 你确定需要长期保留 `1~2` 个以上 warm pod
- 稳态资源已经能吃掉一台小型 ECS worker 的大半
- 用户 sandbox 流量有明显峰谷差

在这个阶段，通常更适合：

- 用 ACK 节点池承接**稳态常驻资源**
- 用 ACS 承接**峰值和不确定流量**

#### 对当前这个项目的直接建议

截至 `2026-03-31`，基于你给出的条件，我**不建议一开始就上 ACK + ACS**。

更合适的顺序是：

1. 现在先用纯 ACS 启动
2. 等你确认前后端与 warm pod 已经形成稳定基线
3. 再升级到 ACK + ACS 混合

原因很简单：

- ACK Pro 有 cluster management fee
- ACS 接入 ACK 也是走 ACK Pro
- 在你的冷启动阶段，这笔固定管理成本和预留节点成本往往还没有被稳态负载摊薄

## 4. 模板设计

### 4.1 设计原则

#### 原则 1：模板必须先命中 ACS 官方规格

启动期的模板不应为了“看起来更细致”而写成 `3.5Gi`、`900m` 这种非原生规格。

#### 原则 2：ACS 阶段不靠 limit 做体验分层

在 ACS 上，`limit > request` 不会带来你在 ACK 上那种“按 request 调度、按 limit 短时突发”的成本优势。

#### 原则 3：ACK 阶段保持 request 不变

ACK 的 burst 只影响 `limit`，不要回头改 request，否则会破坏用户对模板小时与 CU 的理解。

#### 原则 4：所有公开模板保持 `1:4`

这样可以让：

- ACS 成本线性
- ACK 资源规划更直观
- CU 在两种平台上都保持稳定

### 4.2 ACS 启动期模板

统一要求：

- compute class：`general-purpose`
- compute QoS：`default`
- `request = limit`
- 不使用 `pod-required-spec`

| Template | CPU Request | CPU Limit | Memory Request | Memory Limit | CU/h | ACS 官方成本/小时 |
| --- | --- | --- | --- | --- | --- | --- |
| `aio-sandbox-tiny` | `250m` | `250m` | `1Gi` | `1Gi` | `0.25` | `USD 0.010329` |
| `aio-sandbox-small` | `500m` | `500m` | `2Gi` | `2Gi` | `0.5` | `USD 0.020658` |
| `aio-sandbox-medium` | `1` | `1` | `4Gi` | `4Gi` | `1.0` | `USD 0.041316` |
| `aio-sandbox-large` | `2` | `2` | `8Gi` | `8Gi` | `2.0` | `USD 0.082632` |
| `aio-sandbox-xlarge` | `4` | `4` | `16Gi` | `16Gi` | `4.0` | `USD 0.165264` |

建议：

- `large`、`xlarge` 先只保留定义，不做公开自助模板
- 如果后续需要更重的规格，也优先放到 `custom`

### 4.3 ACK 增长期模板

进入 ACK 后，保留同一组 request，再恢复温和的 burst：

| Template | CPU Request | CPU Limit | Memory Request | Memory Limit | CU/h |
| --- | --- | --- | --- | --- | --- |
| `aio-sandbox-tiny` | `250m` | `500m` | `1Gi` | `1536Mi` | `0.25` |
| `aio-sandbox-small` | `500m` | `1000m` | `2Gi` | `3Gi` | `0.5` |
| `aio-sandbox-medium` | `1` | `2` | `4Gi` | `6Gi` | `1.0` |
| `aio-sandbox-large` | `2` | `3` | `8Gi` | `10Gi` | `2.0` |
| `aio-sandbox-xlarge` | `4` | `5` | `16Gi` | `20Gi` | `4.0` |

### 4.4 为什么 ACK 的 request 不跟着变

因为 request 在两个平台里承担的角色是：

- ACS：计费规格的基础输入
- ACK：调度与计量锚点

如果迁移到 ACK 时重新改 request，会导致：

- 同一模板的 CU 变化
- 同一模板的可运行小时数变化
- 既有用户对套餐的理解被打断

因此不建议这么做。

### 4.5 Persistent Sandbox 的一个必须修改点

当前代码里，`persist=true` 的 direct path 会自动把 `limit` 放大到 `2x request`。

这在 ACK 上曾经还能勉强解释成“统一给 burst”，但在 ACS 上不成立，因为：

- ACS 会按 `max(requests, limits)` 规整和计费
- 这会让 persistent sandbox 的**实际计费规格被无意抬高**
- 结果是同一模板下，`persist=false` 和 `persist=true` 的资源口径不一致

因此，本文明确要求：

- **删除代码里统一 `2x request` 推导 limit 的逻辑**
- **persistent sandbox 也必须直接使用 template 中声明的 request / limit**
- ACS 下 template 应为 `request = limit`
- ACK 下 template 可以保留 `limit > request`

这意味着要修改当前实现：

- `treadstone/services/sandbox_service.py`

将 direct path 从“代码推导 limits”改为“模板直接提供 limits”。

### 4.6 Template 应该成为唯一资源真源

无论是 claim path 还是 direct path，最终都应遵循同一条规则：

- **资源规格只在 template 定义**
- 业务代码不再对 CPU / memory 做二次推导

这样有三个好处：

- ACS 与 ACK 的行为一致
- 计量可以直接对齐 template 与实际 pod spec
- persistent sandbox 不会因为代码分支而变成另一套隐式规格

## 5. Compute Unit 设计

### 5.1 定义

统一定义为：

```text
1 CU / hour = 1 vCPU + 4 GiB effective spec
```

### 5.2 统一公式

```text
CU / hour = 0.5 * effective_vCPU + 0.125 * effective_memory_GiB
```

它保留了原方案“加权累加”的优点，同时把“effective spec”补清楚了。

### 5.3 不同平台的 `effective spec`

#### ACS

优先取：

1. `alibabacloud.com/pod-use-spec`
2. 如果未来显式使用 `alibabacloud.com/pod-required-spec`，则按 required spec
3. 都没有时，再退回模板声明值

#### ACK

直接取 pod request。

### 5.4 为什么在 ACS 下不改成别的公式

因为本文推荐的全部公开模板都严格保持 `1:4`：

- `0.25 / 1`
- `0.5 / 2`
- `1 / 4`
- `2 / 8`
- `4 / 16`

因此：

- 每个模板的 `CU/h` 正好是 `0.25 / 0.5 / 1 / 2 / 4`
- 每个模板在 ACS 上的**单位 CU 成本也是线性的**
- 迁移到 ACK 后，用户套餐小时数不需要重新解释

所以，**在考虑 ACS 的情况下，不需要推翻 CU 体系，只需要把“effective billed spec”写清楚并落实到代码里。**

### 5.5 不建议公开提供非 `1:4` 自定义模板

如果未来出现：

- `1 vCPU + 8 GiB`
- `2 vCPU + 4 GiB`

这种偏离 `1:4` 的模板，ACS 成本与 ACK 节点利用率都会变复杂。

结论：

- 公共套餐不开放非 `1:4` 模板
- 非 `1:4` 规格只放到 `custom`

## 6. 持久化存储策略

### 6.1 当前项目里真正使用存储的地方

截至当前代码，真正使用 PVC / 持久卷的是 **persistent sandbox**，不是前端和后端。

当前事实：

- `persist=false`：走 claim path，不带持久卷，可用于 warm pool
- `persist=true`：走 direct path，创建 `Sandbox` CR，并追加 `volumeClaimTemplates`
- 默认存储规格：`5Gi`、`10Gi`、`20Gi`

这意味着你现在的存储模型本质上是：

- **一个 persistent sandbox 对应一块存储**
- 存储生命周期基本绑定 sandbox 生命周期

### 6.2 ACS + Cloud Disk：当前阶段的默认方案

如果目标是：

- 尽快上线
- 少改代码
- 继续沿用当前 `persist=true` 语义

那么最适合你的仍然是 **ACS + cloud disk**。

原因：

- ACS 官方支持 cloud disk 持久化存储
- 你当前 direct path 已经是 `volumeClaimTemplates + ReadWriteOnce`
- 这和 cloud disk 的使用模型天然匹配

结论：

- 启动期默认 persistent storage 方案应为 **ACS + cloud disk**
- `persist=true` 继续表示“给这个 sandbox 附一块独占工作盘”

### 6.3 NAS 能不能避免你现在的权限问题

**有可能部分避免，但不是自动避免。**

ACS 官方对 NAS 的要求里有两条非常关键：

- 如果挂载 NAS，**不要设置 `securityContext.fsgroup`**
- **不能修改 NAS 根目录 `/` 的归属权限**

来源：

- [Use dynamically provisioned NAS volumes in ACS](https://www.alibabacloud.com/help/en/cs/use-nas-dynamic-storage-volumes)

这意味着：

- 如果你现在的权限问题主要来自 **cloud disk 首次挂载后目录归属不对**，NAS 可能可以通过“预先创建目录并设好归属”来绕开
- 但如果你想继续像现在这样依赖 `fsGroup` 在 pod 启动时自动修权限，**NAS 反而不适合**

更准确地说：

- **NAS 不是自动修复权限问题**
- 它是把权限模型从“挂载后动态修”改成“挂载前预置目录权限”

### 6.4 NAS 共享用户存储方案是否可行

**可行，而且在产品方向上是合理的。**

因为 NAS 具备：

- 共享访问能力
- 可被多个 pod 挂载
- 更适合“用户工作区”而不是“单 pod 附盘”

ACS 官方文档也明确说明：

- 同一 NAS 可以挂到多个 pod
- 多 pod 共享同一 NAS 时，应用层需要自己处理并发读写一致性

来源：

- [Use dynamically provisioned NAS volumes in ACS](https://www.alibabacloud.com/help/en/cs/use-nas-dynamic-storage-volumes)

所以，如果你的产品目标是：

1. 用户直接购买存储空间
2. 存储不绑定某个 sandbox
3. 一个用户的多个 persistent sandbox 复用同一工作区

那么 **NAS 比 cloud disk 更符合目标模型**。

### 6.5 但 NAS 方案不是“改个 StorageClass 就行”

如果走 NAS 共享用户存储，这已经不是当前 direct path 的小改，而是**存储架构升级**。

至少要改动这些核心假设：

- 现在：`StorageLedger` 主要按 `sandbox_id` 跟踪
- 未来：需要一个**独立于 sandbox 的用户工作区对象**

建议引入新的概念，例如：

- `WorkspaceVolume`
- 或 `UserWorkspace`

它至少需要表达：

- `owner_id`
- `storage_backend`（`cloud_disk` / `nas`）
- `quota_gib`
- `mount_path` 或 `subpath`
- `status`
- 与 sandbox 的挂载关系

### 6.6 NAS 方案的推荐落地方式

不建议：

- 给所有用户直接挂 NAS 根目录

建议：

- 一块或少量几块 **General-purpose NAS (NFS)** 文件系统
- 每个用户一个独立目录，例如 `/users/<user_id>`
- sandbox 挂载同一 NAS PVC，再通过 `subPath` 进入用户目录

这样做的好处是：

- 存储真正从 sandbox 生命周期中解耦
- 用户换 sandbox 仍然是同一份工作区
- 更适合做“按用户购买存储容量”

### 6.7 NAS 方案下的配额能力与限制

如果你想把“存储容量”做成正式商品，NAS 的 directory quota / user quota 很有价值，但也有官方限制：

- 只支持 **General-purpose NAS + NFS**
- 单个文件系统最多支持 **500 个目录配额**
- 单个目录最多支持 **500 个 UID / GID 配额**
- restrictive quota 生效或取消通常有 **5 到 15 分钟延迟**
- 新建 directory quota 进入 `Initializing` 可能需要**数小时甚至更久**

来源：

- [NAS directory quotas](https://www.alibabacloud.com/help/en/nas/user-guide/manage-directory-quotas)

这意味着：

- 对早期小规模 SaaS，它是可用的
- 但它**不是实时、强同步**的“下单后立刻精确卡死容量”的计费系统

### 6.8 NAS 方案下的权限设计建议

如果未来做 NAS 用户工作区，建议权限策略改成：

- 不再依赖 `fsGroup`
- 不挂 NAS 根目录 `/`
- 预先创建用户子目录
- 在目录创建阶段设定固定 UID / GID 或 ACL

更稳的方式是：

- 通过独立初始化任务或控制面后台任务创建 `/users/<user_id>`
- 再把该目录作为 `subPath` 挂进 sandbox

对于你当前镜像，如果继续固定使用 `UID=1000 / GID=1000`，这是可操作的；但这是**架构推断**，不是 ACS 官方对你业务的直接承诺。

### 6.9 对当前阶段的最终建议

对你现在的阶段，我建议分两步：

#### 现在先做

- ACS + cloud disk
- 保留当前 `persist=true` 功能
- 改掉 persistent sandbox 自动 `2x request` 的资源推导

#### 等产品方向验证后再做

- NAS 用户工作区 V2
- 存储从 `sandbox_id` 解耦到 `owner_id`
- 用户购买的是“工作区容量”，不是“单 sandbox 附盘”

换句话说：

- **cloud disk 适合现在上线**
- **NAS 适合以后把存储产品化**

## 7. Tier 设计

### 7.1 ACS 启动期默认 seed

这是你现在应该真正落地到系统里的默认值。

| Tier | Compute Units / 月 | Storage 容量 | 并发上限 | 最长时长 | Allowed Templates | Grace Period |
| --- | --- | --- | --- | --- | --- | --- |
| `free` | `10` | `0 GiB` | `1` | `7200s` | `aio-sandbox-tiny` | `900s` |
| `pro` | `80` | `10 GiB` | `2` | `28800s` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium` | `3600s` |
| `ultra` | `240` | `30 GiB` | `4` | `86400s` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium` | `10800s` |
| `custom` | `800` | `100 GiB` | `10` | `259200s` | 全部模板，含 `aio-sandbox-large`, `aio-sandbox-xlarge` | `43200s` |

### 7.2 ACS 启动期等效模板小时数

| Tier | Tiny Hours | Small Hours | Medium Hours | Large Hours | XLarge Hours |
| --- | --- | --- | --- | --- | --- |
| `free` | `40` | - | - | - | - |
| `pro` | `320` | `160` | `80` | - | - |
| `ultra` | `960` | `480` | `240` | - | - |
| `custom` | `3200` | `1600` | `800` | `400` | `200` |

### 7.3 为什么 ACS 启动期不把 `large` 开给 `ultra`

原因非常现实：

- 你现在不收费
- ACS 是按秒直接付费
- `large` 的官方小时成本已经是 `USD 0.082632`

如果一上来把 `large` 放给免费 `ultra`，你会过早把最贵的一档成本开放给还没验证成功的用户群。

因此启动期建议：

- `ultra` 仍然比 `pro` 明显更强
- 但主要强在额度、时长、并发
- `large` 先收口到 `custom`

### 7.4 ACK 增长期目标值

等你迁到 ACK，或者至少进入 ACK+ACS 混合期后，再切换到这组目标值：

| Tier | Compute Units / 月 | Storage 容量 | 并发上限 | 最长时长 | Allowed Templates | Grace Period |
| --- | --- | --- | --- | --- | --- | --- |
| `free` | `20` | `0 GiB` | `1` | `7200s` | `aio-sandbox-tiny` | `900s` |
| `pro` | `160` | `20 GiB` | `3` | `86400s` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium` | `7200s` |
| `ultra` | `480` | `100 GiB` | `8` | `259200s` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium`, `aio-sandbox-large` | `21600s` |
| `custom` | `1600` | `250 GiB` | `20` | `604800s` | 全部模板，含 `aio-sandbox-xlarge` | `86400s` |

### 7.5 welcome bonus 必须调整

当前代码里 `free` 用户自动获得：

- `50 CU`
- 有效期 `90` 天

在 ACS 启动期，这个默认值已经不合理，因为：

- `free` 本身只有 `10 CU`
- 额外 `50 CU` 等于把默认试用额度放大到 `6x`
- 这和你现在“先免费运营、但要控风险”的目标是冲突的

建议：

- 默认关闭自动 welcome bonus
- 如果要做活动，改成管理员显式发 `ComputeGrant`

## 8. 收费标准

### 8.1 启动期实际收费

你现在可以直接这样做：

- `free = ¥0`
- `pro = ¥0`
- `ultra = ¥0`

但这只应作为：

- 冷启动促销
- 邀请测试
- 人工筛选种子用户

而不是长期公开价格。

### 8.2 未来建议公开标价

建议未来正式开放付费时采用：

| Plan | 建议标价 | 适用阶段 |
| --- | --- | --- |
| `free` | `¥0 / 月` | 长期保留 |
| `pro` | `¥99 / 月` | 第一档公开付费套餐 |
| `ultra` | `¥299 / 月` | 第二档公开付费套餐 |
| `custom` | `¥999 / 月` 起 | 人工报价 |

### 8.3 这些价格为什么合理

先看 ACS 启动期的理论变量计算成本。按官方 general-purpose / default、香港与海外价格：

- `1 CU / 月` 约等于 `USD 0.041316`
- `pro 80 CU` 约等于 `USD 3.31`
- `ultra 240 CU` 约等于 `USD 9.92`
- `custom 800 CU` 约等于 `USD 33.05`

这些只是：

- 纯 vCPU / 内存成本

还**不包括**：

- SLB / EIP / NAT Gateway
- 公网流量
- 持久存储
- 日志与监控
- 控制面与运维时间成本

因此：

- 启动期免费没问题，但要靠额度控风险
- 未来 `¥99 / ¥299` 的公开价格仍然留有足够安全边际

### 8.4 如果付费上线时你仍然还在 ACS

如果到公开收费时你仍然完全运行在 ACS 上，建议：

- 先沿用 **ACS 启动期额度**
- 不要立刻切到 ACK 增长期额度

只有满足以下任一条件后，再切：

- 已经迁到 ACK 或 ACK+ACS 混合期
- 连续一个计费周期看到了明显的套餐闲置率
- 你确认当前价格下的单位经济成立

## 9. 模板开放与 warm pool 策略

### 8.1 ACS 启动期

#### 公开自助模板

- `tiny`
- `small`
- `medium`

#### 仅人工放行

- `large`
- `xlarge`

#### warm pool

- 默认全部关闭
- 如确有必要，仅允许 `tiny` 在白天保留 `1` 个

原因：

- ACS 从镜像下载开始就计费
- warm pool 不是“空着不花钱”，而是真成本

### 8.2 ACK 增长期

#### 公开自助模板

- `tiny`
- `small`
- `medium`
- `large`

#### 仅人工放行

- `xlarge`

#### warm pool

- `tiny`: `1~2`
- `small` 及以上：默认关闭

## 10. 迁移建议

### 9.1 推荐迁移顺序

1. 现在先上 ACS
2. 用户稳定后，创建 ACK Pro
3. 将 API / Web / 控制面先迁到 ACK
4. 增加一组 `1:4` 的 ECS worker 节点
5. 再把主力 sandbox 流量迁到 ACK 节点池
6. 最后按需保留 ACS virtual node 处理峰值

### 9.2 模板如何迁移

迁移时不要改：

- 模板名称
- request 梯度
- CU 定义
- Tier 名称

迁移时只改：

- 运行平台
- `limit`
- warm pool
- `large` 的开放范围

这能让用户感知到的是“体验更好”，而不是“套餐定义变了”。

## 11. 实施影响

### 10.1 计量实现

需要改：

- `treadstone/services/metering_helpers.py`
- `treadstone/services/metering_service.py`
- `treadstone/api/usage.py`

要求：

- 支持从 ACS pod annotation 读取 `effective billed spec`
- 如果没有 annotation，再退回模板 request

### 10.2 模板静态表与 Helm values

需要改：

- `deploy/sandbox-runtime/values.yaml`
- `deploy/sandbox-runtime/values-local.yaml`
- `deploy/sandbox-runtime/values-demo.yaml`
- `deploy/sandbox-runtime/values-prod.yaml`
- `treadstone/services/metering_helpers.py`
- `treadstone/services/k8s_client.py`

建议新增平台开关：

- `sandboxPlatform = acs | ack`
- `sandboxStorageMode = cloud_disk | nas`

### 10.3 Persistent Storage 修改点

需要改：

- `treadstone/services/sandbox_service.py`
- `treadstone/services/k8s_client.py`
- `deploy/cluster-storage/*`
- `docs/zh-CN/modules/02-sandbox-lifecycle-and-templates.md`

要求：

- direct path 不再自动 `2x request` 推导 limit
- direct path 改为直接读取 template 声明的 limits
- ACS 的 persistent sandbox 默认走 `cloud_disk`
- 如果未来启用 NAS，共享工作区必须引入独立于 sandbox 的存储对象，而不是继续复用当前 `sandbox_id -> PVC` 模型

### 11.4 Tier 默认值与 welcome bonus

需要改：

- 新增 migration，把默认 seed 改成 ACS 启动期值
- 关闭自动 `50 CU / 90 天` welcome bonus

### 11.5 文档同步

需要同步至少：

- `README.md`
- `docs/zh-CN/modules/02-sandbox-lifecycle-and-templates.md`
- `docs/zh-CN/modules/05-metering-and-admin-ops.md`
- `docs/zh-CN/modules/05-metering-system-audit.md`
- `web/public/docs/getting-started.md`

## 12. 最终建议

如果只保留一句话作为执行结论，就是：

**现在按 ACS 启动期落地：模板改成 `request = limit` 的精确支持规格，persistent sandbox 取消代码里的自动 `2x request` 推导并改为直接使用 template，CU 改成基于 `effective billed spec`，默认 Tier 收紧到 `free 10 / pro 80 / ultra 240 / custom 800`，关闭自动 welcome bonus；未来升级到 ACK 时，保留同一组 request 与 CU，只恢复 burst limit。至于用户级共享存储，建议作为 NAS 工作区 V2 单独设计，而不是在当前 `sandbox -> PVC` 模型上硬改。**
