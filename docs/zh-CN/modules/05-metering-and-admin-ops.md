# 模块 5：计量、套餐与管理员运营

## 模块目标

这个模块负责：

- 记录用户的 compute / storage 使用情况
- 表达套餐与配额
- 给普通用户提供 usage 视图
- 给管理员提供 plan / grant / tier template 管理接口

当前实现主要位于：

- `treadstone/models/metering.py`
- `treadstone/services/metering_service.py`
- `treadstone/services/metering_tasks.py`
- `treadstone/api/usage.py`
- `treadstone/api/admin.py`
- `alembic/versions/9f3a6a152a5c_add_metering_tables.py`

## 1. 当前数据模型

### 套餐模板

- `TierTemplate`

定义系统级默认套餐模板。

### 用户套餐快照

- `UserPlan`

表示用户当前真正生效的套餐限制和使用状态，而不是只读地引用模板。

### 额外额度

- `CreditGrant`

用于 welcome bonus、管理员发放、营销活动等额外额度。

### 计算用量

- `ComputeSession`

记录某个 sandbox 一次运行区间内的计算额度消耗。

### 存储用量

- `StorageLedger`

记录持久卷的分配、释放与累计的 `gib_hours_consumed`。

## 2. 当前内置 Tier

迁移脚本里真实 seed 的 Tier 如下：

| Tier | Compute/月 | Storage/月 | 并发上限 | 最长时长 | 允许规格 | Grace Period |
| --- | --- | --- | --- | --- | --- | --- |
| `free` | `10` | `0` | `1` | `1800s` | `tiny`, `small` | `600s` |
| `pro` | `100` | `10` | `3` | `7200s` | `tiny`, `small`, `medium` | `1800s` |
| `ultra` | `300` | `20` | `5` | `28800s` | `tiny`, `small`, `medium`, `large` | `3600s` |
| `enterprise` | `5000` | `500` | `50` | `86400s` | `tiny`, `small`, `medium`, `large`, `xlarge` | `7200s` |

另外，free 用户第一次创建 plan 时会自动获得：

- `50` compute credits 的 welcome bonus
- 默认有效期 `90` 天

## 3. 当前用户接口

普通用户可见的计量接口有：

- `GET /v1/usage`
- `GET /v1/usage/plan`
- `GET /v1/usage/sessions`
- `GET /v1/usage/grants`

这些接口会返回：

- 当前 tier
- 当前计费周期起止
- 月度 compute 配额与已用量
- extra credits 剩余量
- storage 配额与已用量
- 并发限制
- 最长运行时长
- grace period 状态

## 4. 当前管理员接口

管理员接口集中在 `/v1/admin/*`：

- `GET /v1/admin/tier-templates`
- `PATCH /v1/admin/tier-templates/{tier_name}`
- `GET /v1/admin/users/{user_id}/usage`
- `PATCH /v1/admin/users/{user_id}/plan`
- `POST /v1/admin/users/{user_id}/grants`
- `POST /v1/admin/grants/batch`

这些接口已经是当前代码中的真实运营能力，不再只是设计稿。

## 5. 后台任务

当前计量后台任务每 `60` 秒 tick 一次，主要做四类工作：

- 递增 open `ComputeSession` 的消耗
- 递增 active `StorageLedger` 的 `gib_hours_consumed`
- 检查 80% / 100% warning 阈值
- 检查 grace period 并在必要时自动 stop sandbox
- 月度 reset `UserPlan` 的周期字段和月度使用量

## 6. 当前实现现状

### 已落地部分

- 数据模型已经完整存在
- 用户 usage API 已存在
- 管理员套餐/额度 API 已存在
- 后台 tick、warning、grace period、月度 reset 已存在
- K8s 状态同步会 best-effort 打开/关闭 `ComputeSession`

### 还没有变成完整闭环的部分

当前代码里有两个需要明确写在文档里的现实：

1. **计量模块的规格命名仍然使用 `tiny/small/medium/large/xlarge`**
2. **Sandbox 控制面创建接口实际使用的是 `aio-sandbox-*` 模板名**

这两套命名尚未统一，因此计量文档不能再把它写成已经完全收敛的一个体系。

另外，`SandboxService` 已经有：

- `check_template_allowed`
- `check_compute_quota`
- `check_concurrent_limit`
- `check_storage_quota`
- `check_sandbox_duration`

这些接入点，但当前公开的 `sandboxes` 路由还没有把 `MeteringService` 注入进去，所以**“公开 API 上的配额执行”仍属于部分接线状态**。

## 7. 当前明确未实现的内容

旧文档里和计量一起出现过的下列能力，当前仓库还没有：

- Stripe Checkout
- 支付 webhook
- 发票 / 钱包 / 充值
- 真正的 Billing 系统闭环

因此当前文档把这一块描述为“计量与运营基础设施”，而不是“已完成的商业计费系统”。

