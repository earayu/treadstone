---
此文档已废弃，暂不准备实现
---

# Phase 3：付款与计量 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现沙箱使用时长计量和 Stripe 集成付款，支持按量计费。

**Architecture:** 沙箱创建/销毁时记录时间戳到 DB → 计量服务计算用量 → Stripe 处理支付。用户有配额（免费额度 + 付费额度），超限自动停止沙箱。

**Tech Stack:** Stripe Python SDK, FastAPI, SQLAlchemy async

---

### Task 1：计量数据模型

**Files:**
- Create: `treadstone/models/billing.py`
- Alembic migration

**要点：**
- `UsageRecord` 表：sandbox_id, started_at, ended_at, duration_seconds
- `UserQuota` 表：user_id, free_seconds_remaining, paid_seconds_remaining
- 沙箱创建时写 started_at，销毁时写 ended_at 并计算 duration

**Commit:** `feat: billing data models (usage record + user quota)`

---

### Task 2：计量 Service

**Files:**
- Create: `treadstone/services/billing_service.py`
- Test: `tests/test_billing_service.py`

**要点：**
- `record_start(sandbox_id)` — 沙箱创建时调用
- `record_stop(sandbox_id)` — 沙箱销毁时调用，计算 duration，扣减配额
- `check_quota(user_id) -> bool` — 检查用户是否有剩余配额
- `get_usage_summary(user_id) -> dict` — 返回用量统计

在 SandboxService 的 create/delete 方法中调用计量 service。

**Commit:** `feat: usage metering service`

---

### Task 3：Stripe 集成

**Files:**
- Create: `treadstone/core/stripe_client.py`
- Create: `treadstone/api/billing.py`
- Test: `tests/test_billing_api.py`

**要点：**
- 添加依赖：`uv add stripe`
- `POST /api/billing/checkout` — 创建 Stripe Checkout Session
- `POST /api/billing/webhook` — Stripe webhook，支付成功后增加用户配额
- `GET /api/billing/usage` — 查询用量和余额
- config.py 添加 `stripe_secret_key` 和 `stripe_webhook_secret`

**Commit:** `feat: stripe integration with checkout and webhook`

---

### Task 4：配额超限自动停止

**Files:**
- Modify: `treadstone/services/sandbox_service.py`

**要点：**
- 创建沙箱前检查 `check_quota(user_id)`，不足则返回 402 Payment Required
- 后台定期检查运行中沙箱的用户配额（FastAPI BackgroundTasks 或 K8s CronJob）
- 配额耗尽时自动停止该用户所有运行中沙箱

**Commit:** `feat: quota enforcement on sandbox creation`
