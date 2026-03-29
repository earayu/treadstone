# 模块 5：计量、套餐与管理员运营

## 模块目标

这个模块负责：

- 记录用户的 Compute / Storage 使用情况
- 表达套餐模板、用户计划与管理员授予
- 对普通用户提供 usage / plan / grants 视图
- 对管理员提供 tier template、user plan、compute grant、storage quota grant 的管理接口
- 在需要时对 sandbox create / start 执行配额限制

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
- `treadstone/api/sandbox_templates.py`
- `alembic/versions/9f3a6a152a5c_add_metering_tables.py`
- `alembic/versions/f7a1b3c5d9e2_normalize_allowed_templates_to_full_.py`
- `alembic/versions/c4d5e6f7a8b9_metering_system_overhaul.py`
- `alembic/versions/d7e8f9a0b1c2_split_credit_grant_into_compute_and_storage.py`
- `alembic/versions/e1a2b3c4d5f6_rename_credits_to_compute_units.py`

## 1. 当前数据模型

### 套餐模板

- `TierTemplate`

系统级默认套餐模板，定义：

- 月度 Compute Units
- Storage 容量上限
- 并发上限
- 最长运行时长
- 允许模板
- grace period

### 用户套餐快照

- `UserPlan`

用户当前真正生效的套餐限制和状态，不是只读引用模板，而是“模板快照 + override + 当前周期状态”。

### Compute 授予

- `ComputeGrant`

可消费的额外 Compute Unit 池，典型用途：

- welcome bonus
- 管理员补偿
- 活动赠送

### Storage 授予

- `StorageQuotaGrant`

额外存储容量 entitlement，不随使用时间递减，只影响总 Storage 配额上限。

### 计算用量

- `ComputeSession`

记录某个 sandbox 一段运行区间内的：

- 模板
- vCPU / Memory 规格快照
- 原始资源小时
- 对应的 Compute Unit 小时

### 存储用量

- `StorageLedger`

记录持久卷的：

- 分配
- 释放
- 当前状态
- 累计 `gib_hours_consumed`

## 2. 当前计量模型

### Compute

Compute 当前是“两层模型”：

1. **实际使用量**
   - `ComputeSession.vcpu_hours`
   - `ComputeSession.memory_gib_hours`
   - `UsageSummary.compute.compute_unit_hours`
2. **entitlement 池**
   - `UserPlan.compute_units_monthly_limit`
   - `UserPlan.compute_units_monthly_used`
   - `ComputeGrant.remaining_amount`

Compute Unit 公式：

```text
CU / hour = max(vCPU_request, memory_GiB_request / 2)
```

消费顺序：

1. 月度池
2. ComputeGrant FIFO 池

### Storage

Storage 当前也是两层：

1. **容量**
   - `current_used_gib`
   - `total_quota_gib`
2. **时间累计**
   - `gib_hours_consumed`

Storage 当前模型是“容量 entitlement + 生命周期 GiB-hours 累计”，而不是消费型 credits。

## 3. 当前内置 Tier

迁移脚本里真实 seed 的 Tier 如下：

| Tier | Compute Units / 月 | Storage 容量 | 并发上限 | 最长时长 | 允许规格 | Grace Period |
| --- | --- | --- | --- | --- | --- | --- |
| `free` | `10` | `0 GiB` | `1` | `1800s` | `aio-sandbox-tiny`, `aio-sandbox-small` | `600s` |
| `pro` | `100` | `10 GiB` | `3` | `7200s` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium` | `1800s` |
| `ultra` | `300` | `20 GiB` | `5` | `28800s` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium`, `aio-sandbox-large` | `3600s` |
| `enterprise` | `5000` | `500 GiB` | `50` | `86400s` | `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium`, `aio-sandbox-large`, `aio-sandbox-xlarge` | `7200s` |

另外，free 用户第一次创建 `UserPlan` 时会自动获得：

- `50` Compute Units 的 welcome bonus
- 默认有效期 `90` 天

## 4. 当前用户接口

普通用户可见的计量接口有：

- `GET /v1/usage`
- `GET /v1/usage/plan`
- `GET /v1/usage/sessions`
- `GET /v1/usage/storage-ledger`
- `GET /v1/usage/grants`

这些接口返回的不是纯 usage，也不是纯 quota，而是：

- 实际 Compute 用量
- entitlement 池状态
- Storage 当前容量视图
- grants 列表
- 并发 / 时长 / 模板限制
- grace period 状态

## 5. 当前管理员接口

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

## 6. 当前后台任务

当前计量后台任务由 leader 副本驱动。

### 每 60 秒

- `tick_metering()`
- `tick_storage_metering()`
- `check_warning_thresholds()`
- `check_grace_periods()`
- `reset_monthly_credits()`

### 每 300 秒

- `reconcile()`
- `reconcile_metering()`
- `reconcile_storage_metering()`
- `sync_template_specs_from_k8s()`
- `validate_template_specs()`

## 7. 当前实现现状

### 已经形成闭环的部分

- 公开 `sandboxes` 路由已经接入 `MeteringService`
- Compute 的双池消费已经接回真实运行链路
- Storage 已按容量和 GiB-hours 记账
- Storage Reconcile 已存在
- Usage/Admin API 已对齐 `compute_units`
- E2E Hurl 已基本对齐新接口

### 当前仍然要注意的缺陷

当前第三轮审计确认，最重要的现实问题不是“主链路没接上”，而是以下几项：

1. **`compute_session` 没有 active 唯一约束，Watch / Reconcile 并发时理论上可能重复开 session**
2. **Storage `gib_hours` 仍然是生命周期累计，不是严格按 billing period 切分**
3. **persistent sandbox 删除时会先释放 StorageLedger，再尝试删除 K8s 资源，删除失败会导致 quota 过早释放**
4. **grace 期间的 overage 没有持久化，absolute overage cap 规则在真实路径下几乎无法生效**

## 8. 当前适合怎样对外表述

当前更适合把这套系统定义为：

- **计量 + 配额 + 运营基础设施**

而不是：

- **严格账务级 billing system**

如果需要上线前逐项核对数据流程、函数、接口、数据库与缺陷，请直接看详细审计文档：

- [`05-metering-system-audit.md`](./05-metering-system-audit.md)
