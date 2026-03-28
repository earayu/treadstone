# 模块 5：计量、套餐与管理员运营

## 模块目标

这个模块负责：

- 记录用户的 compute / storage 使用情况
- 表达套餐、用户计划与授予（grant）
- 给普通用户提供 usage / plan / grants 视图
- 给管理员提供 tier template、user plan、compute grant、storage grant 管理接口

如果需要一份面向上线前审计、严格按当前代码逐项核对的超详细报告，见：

- [`05-metering-system-audit.md`](./05-metering-system-audit.md)

当前实现主要位于：

- `treadstone/models/metering.py`
- `treadstone/services/metering_service.py`
- `treadstone/services/metering_tasks.py`
- `treadstone/services/k8s_sync.py`
- `treadstone/services/sync_supervisor.py`
- `treadstone/services/metering_helpers.py`
- `treadstone/services/sandbox_service.py`
- `treadstone/api/usage.py`
- `treadstone/api/admin.py`
- `treadstone/api/sandboxes.py`
- `alembic/versions/9f3a6a152a5c_add_metering_tables.py`
- `alembic/versions/f7a1b3c5d9e2_normalize_allowed_templates_to_full_.py`
- `alembic/versions/c4d5e6f7a8b9_metering_system_overhaul.py`
- `alembic/versions/d7e8f9a0b1c2_split_credit_grant_into_compute_and_storage.py`

## 1. 当前数据模型

### 套餐模板

- `TierTemplate`

定义系统级默认套餐模板。

### 用户套餐快照

- `UserPlan`

表示用户当前真正生效的套餐限制和使用状态，而不是只读地引用模板。

### Compute 授予

- `ComputeGrant`

用于 welcome bonus、管理员发放、营销活动等额外 compute entitlement。

### Storage 授予

- `StorageQuotaGrant`

表示额外的存储容量上限，而不是消费型余额。

### 计算用量

- `ComputeSession`

记录某个 sandbox 一次运行区间内的原始资源用量：

- `vcpu_request`
- `memory_gib_request`
- `vcpu_hours`
- `memory_gib_hours`

### 存储用量

- `StorageLedger`

记录持久卷的分配、释放与累计的 `gib_hours_consumed`。

## 2. 当前内置 Tier

迁移脚本里真实 seed 的 Tier 如下：

| Tier | Compute/月 | Storage 容量 | 并发上限 | 最长时长 | 允许规格 | Grace Period |
| --- | --- | --- | --- | --- | --- | --- |
| `free` | `10` | `0 GiB` | `1` | `1800s` | `aio-sandbox-tiny`, `aio-sandbox-small` | `600s` |
| `pro` | `100` | `10 GiB` | `3` | `7200s` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium` | `1800s` |
| `ultra` | `300` | `20 GiB` | `5` | `28800s` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium`, `aio-sandbox-large` | `3600s` |
| `enterprise` | `5000` | `500 GiB` | `50` | `86400s` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium`, `aio-sandbox-large`, `aio-sandbox-xlarge` | `7200s` |

另外，free 用户第一次创建 plan 时会自动获得：

- `50` compute credits 的 welcome bonus
- 默认有效期 `90` 天

## 3. 当前用户接口

普通用户可见的计量接口有：

- `GET /v1/usage`
- `GET /v1/usage/plan`
- `GET /v1/usage/sessions`
- `GET /v1/usage/storage-ledger`
- `GET /v1/usage/grants`

这些接口会返回：

- 当前 tier
- 当前计费周期起止
- compute 原始用量（`vcpu_hours` / `memory_gib_hours`）
- plan 中的月度 compute limit 与当前 monthly used
- compute grants 与 storage quota grants
- storage 当前容量使用与总配额
- 并发限制
- 最长运行时长
- grace period 状态

## 4. 当前管理员接口

管理员接口集中在 `/v1/admin/*`：

- `GET /v1/admin/tier-templates`
- `PATCH /v1/admin/tier-templates/{tier_name}`
- `GET /v1/admin/users/lookup-by-email`
- `POST /v1/admin/users/resolve-emails`
- `GET /v1/admin/users/{user_id}/usage`
- `PATCH /v1/admin/users/{user_id}/plan`
- `POST /v1/admin/users/{user_id}/compute-grants`
- `POST /v1/admin/users/{user_id}/storage-grants`
- `POST /v1/admin/compute-grants/batch`
- `POST /v1/admin/storage-grants/batch`

这些接口已经是当前代码中的真实运营能力，不再只是设计稿。

## 5. 后台任务

当前计量后台任务每 `60` 秒 tick 一次，主要做四类工作：

- 递增 open `ComputeSession` 的原始资源小时
- 递增 active `StorageLedger` 的 `gib_hours_consumed`
- 检查 80% / 100% warning 阈值
- 检查 grace period 并在必要时自动 stop sandbox
- 月度 reset `UserPlan` 的周期字段和月度使用量

除此之外，K8s 状态同步层还会：

- 近实时 Watch Sandbox CR 状态
- 每 `300` 秒做一次 reconcile
- 修复 `ComputeSession` 与 `StorageLedger` 的漏记/孤儿状态

## 6. 当前实现现状

### 已落地部分

- 公开 `sandboxes` 路由已经注入 `MeteringService`
- 数据模型已经拆成 `ComputeGrant` 与 `StorageQuotaGrant`
- Compute 已按原始资源小时记账
- Storage 已按容量与 GiB-hours 记账
- Storage reconcile 已存在
- Usage/Admin API 已存在
- 后台 tick、warning、grace period、月度 reset 已存在

### 仍然没有形成完整闭环的部分

当前代码里最关键的现实是：

1. **公开请求路径虽然已经能做 metering enforcement，但默认受 `TREADSTONE_METERING_ENFORCEMENT_ENABLED=false` 控制**
2. **Compute 的原始 usage 已经会增长，但 `consume_compute_credits()` 没有生产调用链**
3. **因此 `compute_credits_monthly_used` 与 `ComputeGrant.remaining_amount` 不会随真实运行自然变化**
4. **warning / grace period / auto-stop 仍依赖上述 credit 字段，所以当前 Compute 超额执行链路并未闭环**

也就是说：

- Storage 这条线比 Compute 更接近可上线状态
- Compute 当前更像“原始 usage 观测系统 + 未完成的 credit enforcement 框架”

## 7. 当前明确未实现的内容

旧文档里和计量一起出现过的下列能力，当前仓库还没有：

- Stripe Checkout
- 支付 webhook
- 发票 / 钱包 / 充值
- 真正的 Billing 系统闭环

因此当前文档把这一块描述为“计量与运营基础设施”，而不是“已完成的商业计费系统”。
