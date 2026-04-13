# E2E 测试重新设计方案

> 作者: @archi-opus-46 | 日期: 2026-04-14
> 背景: 模块重构(PR #324)完成后，对 E2E 测试进行全面升级

---

## 1. 现状分析

### 1.1 端点清单（88 个）

经完整代码审查，Treadstone 共有 **88 个 API 端点**，分布在 14 个模块：

| 模块 | 端点数 | 说明 |
|------|--------|------|
| Auth（认证） | 21 | 注册/登录/登出/OAuth/密码/验证/用户状态/删除 |
| API Keys | 4 | CRUD + scope 控制 |
| CLI Auth | 6 | flow 创建/轮询/exchange/browser approve |
| Browser Auth | 2 | bootstrap + login redirect |
| Sandboxes | 11 | CRUD + start/stop/snapshot/web-link |
| Sandbox Proxy | 2 | HTTP 全方法代理 + WebSocket |
| Templates | 1 | sandbox 模板列表 |
| Usage | 5 | usage/plan/sessions/storage-ledger/grants |
| Admin | 19 | stats/limits/tiers/users/grants/waitlist/feedback/force-reset |
| Audit | 2 | events + filter-options |
| Support | 1 | feedback 提交 |
| Waitlist | 1 | 申请提交 |
| Config | 1 | 应用配置 |
| System | 1 | health check |
| Docs | 2 | sitemap + doc pages |
| **合计** | **88** | |

### 1.2 现有 10 个 E2E 测试覆盖情况

| 文件 | 测试内容 | 覆盖端点数 |
|------|----------|-----------|
| 01-auth-flow | 注册→登录→获取用户 | 3 |
| 02-api-keys | key 创建/列表/Bearer 认证/删除 | 5 |
| 03-password-change | 改密→新密码登录 | 3 |
| 04-sandbox-crud | 邮箱验证→sandbox 创建/查看/列表/删除 | 10 |
| 05-sandbox-dual-path | claim vs direct 路径 + storage grant | ~15 |
| 06-sandbox-names-web-link | 命名冲突 + web-link + 跨用户隔离 | ~12 |
| 07-metering-usage | usage/plan/sessions/grants + 非 admin 权限拒绝 | 6 |
| 08-metering-admin | tier template 管理 + 用户升级 + grant 发放 | 8 |
| 09-data-plane-proxy | 代理认证 + scope 执法 + shell exec | 7 |
| 10-sandbox-lifecycle | 完整生命周期: create→ready→stop→start→delete | 7 |

**已覆盖:** ~40 个端点（约 45%）
**完全未覆盖:** ~48 个端点（约 55%）

### 1.3 主要覆盖缺口

**零覆盖模块：**
- CLI Auth 全部 6 个端点
- Browser Auth 全部 2 个端点
- Docs 全部 2 个端点
- Support feedback 提交
- Waitlist 申请提交
- Audit events 查询和过滤

**部分覆盖缺口：**
- Admin: stats、platform-limits、用户查找/解析/禁用/删除、waitlist 管理、support feedback 查看、force-reset — 均未测
- Sandbox: PATCH（更新 labels/auto_stop 等）、snapshot 触发、web-link DELETE — 未测
- Usage: storage-ledger — 未测
- API Key: PATCH（更新 key）— 未测
- Auth: set-password（OAuth 用户）、password-reset 流程、OAuth 回调 — 未测

**场景缺口：**
- 负面测试：无效凭证、重复注册、畸形请求 — 极少
- 跨用户隔离：仅 06 测试了命名，sandbox 可见性隔离不完整
- 并发配额执法：现有测试刻意避开 max_concurrent_running 限制
- API key scope 细粒度测试：仅测了 CP-only，未测 data_plane.mode=sandbox 等

---

## 2. 设计原则

1. **按业务流程组织**，而非按 API 端点——每个文件讲一个完整的用户故事
2. **每个文件独立运行**——自带注册/登录，不依赖文件执行顺序，支持并行
3. **正面 + 负面路径**——每个核心流程都包含成功路径和关键错误路径
4. **现有好测试保留**——04-06 已经很好，调整而非重写；01-03 可强化
5. **变量命名约定**——`email_NN` 对应文件编号，保持 `e2e-test.sh` 变量注入模式

---

## 3. 新版测试文件规划

### 总览：21 个文件

| 编号 | 文件名 | 优先级 | 来源 | 新增端点 |
|------|--------|--------|------|---------|
| 01 | auth-session.hurl | P0 | 改写现有01 | +3 |
| 02 | auth-apikey.hurl | P0 | 改写现有02 | +2 |
| 03 | auth-password.hurl | P0 | 改写现有03 | +3 |
| 04 | sandbox-crud.hurl | P0 | 保留现有04 | 0 |
| 05 | sandbox-dual-path.hurl | P0 | 保留现有05 | 0 |
| 06 | sandbox-names-web-link.hurl | P0 | 小改现有06 | +1 |
| 07-10 | (现有文件保留不动) | — | 保留 | 0 |
| 11 | sandbox-lifecycle-ephemeral.hurl | P1 | 全新 | +4 |
| 12 | sandbox-lifecycle-persistent.hurl | P1 | 全新 | +5 |
| 13 | sandbox-quota-enforcement.hurl | P1 | 全新 | +3 |
| 14 | metering-usage-extended.hurl | P1 | 全新 | +2 |
| 15 | data-plane-proxy-extended.hurl | P1 | 全新 | +2 |
| 16 | cli-auth-flow.hurl | P2 | 全新 | +6 |
| 17 | admin-platform.hurl | P2 | 全新 | +8 |
| 18 | audit-events.hurl | P2 | 全新 | +2 |
| 19 | sandbox-patch-snapshot.hurl | P2 | 全新 | +3 |
| 20 | waitlist-support.hurl | P3 | 全新 | +4 |
| 21 | error-boundaries.hurl | P3 | 全新 | +5 |

> 注：编号 11-15 由 @dev-claude-opus-46 在 P1 实现中使用，P2/P3 文件顺延至 16-21。
> 07-10 原有文件保留不动，新增测试场景通过 11-15 独立文件覆盖。

---

### 3.1 P0 — 核心路径（必须，第一轮）

#### 01-auth-register-login.hurl（改写）

**当前:** 注册→登录→获取用户，共 3 步。

**改为:**
```
1. GET /health → 200（服务就绪门控）
2. POST /v1/auth/register → 201（注册新用户）
3. POST /v1/auth/register 同一 email → 409（重复注册拒绝）
4. POST /v1/auth/login → 200（登录，获取 session cookie）
5. GET /v1/auth/user → 200（获取当前用户，验证字段）
6. POST /v1/auth/logout → 200（登出）
7. GET /v1/auth/user（无 cookie）→ 401（登出后无法访问）
8. POST /v1/auth/login → 200（重新登录成功）
```

**新增覆盖:** 重复注册 409、登出、登出后 401。

#### 02-auth-apikey-scope.hurl（改写）

**当前:** 创建/列表/Bearer 认证/删除。

**改为:**
```
1. 注册→登录
2. POST /v1/auth/api-keys（默认 scope）→ 201
3. GET /v1/auth/api-keys → 200（列表，验证 ≥1）
4. GET /v1/auth/user（Bearer token）→ 200（验证 Bearer 认证）
5. PATCH /v1/auth/api-keys/{id}（改名）→ 200（更新 key 名称）
6. POST /v1/auth/api-keys（scope: control_plane=false, data_plane.mode=sandbox）→ 201
7. GET /v1/auth/api-keys（Bearer，受限 key）→ 403（control_plane=false 访问 CP 端点）
8. DELETE /v1/auth/api-keys/{id} → 204
9. GET /v1/auth/user（Bearer，已删除 key）→ 401（已删除 key 不可用）
```

**新增覆盖:** PATCH 更新 key、受限 scope 403、已删除 key 401。

#### 03-auth-password.hurl（改写）

**当前:** 改密→新密码登录，共 4 步。

**改为:**
```
1. 注册→登录
2. POST /v1/auth/change-password → 200（改密）
3. POST /v1/auth/login（旧密码）→ 400（旧密码失效，BadRequestError）
4. POST /v1/auth/login（新密码）→ 200（新密码登录成功）
5. POST /v1/auth/password-reset/request → 200（请求重置）
6. 通过 admin API 获取重置 token（或直接 mock）
7. POST /v1/auth/password-reset/confirm → 200（确认重置）
8. POST /v1/auth/login（重置后密码）→ 200
```

**新增覆盖:** 旧密码失效验证、密码重置完整流程。

> 注意: password-reset 需要邮件 token。在 E2E 环境中，`TREADSTONE_EMAIL_BACKEND=memory`，可通过 admin API `GET /v1/admin/verification-token-by-email` 间接获取，或根据实现情况决定是否跳过。如果重置 token 无法在 E2E 中获取，此部分标记为 P2。

#### 04-sandbox-crud-verify.hurl — 保留现有，无需修改

现有测试已很完整：邮箱验证→创建→查看→列表→删除。

#### 05-sandbox-dual-path.hurl — 保留现有，无需修改

claim vs direct 路径、storage grant、模板验证，覆盖良好。

#### 06-sandbox-names-weblink.hurl（小改）

**新增一步:**
```
在 User A 删除 sandbox 之前，增加：
- DELETE /v1/sandboxes/{id}/web-link → 200（主动撤销 web-link）
- GET /v1/sandboxes/{id}/web-link → 验证 enabled: false
```

**新增覆盖:** web-link 主动撤销（DELETE）。

---

### 3.2 P1 — 重要路径（第二轮）

#### 07-metering-usage.hurl（扩展）

**现有基础上增加:**
```
增加 storage-ledger 验证（需要 persistent sandbox 前置）：
- GET /v1/usage/storage-ledger → 200（验证 ledger 记录存在）

增加 grants 非空验证（在 admin 发放 grant 后）：
- GET /v1/usage/grants → 200（验证 compute_grants count > 0）
```

**注意:** storage-ledger 测试依赖 persistent sandbox，可能需要跨文件共享，或在本文件内自行创建 persistent sandbox。考虑到独立性原则，建议本文件内创建。

#### 08-metering-admin.hurl（扩展）

**现有基础上增加:**
```
- POST /v1/admin/users/{id}/storage-grants → 201（单个 storage grant）
- POST /v1/admin/storage-grants/batch → 200（批量 storage grant）
```

**新增覆盖:** storage grant 单个和批量。

#### 09-data-plane-proxy.hurl — 保留现有，无需修改

已有完整的认证 + scope 执法 + shell exec 测试。

#### 10-sandbox-lifecycle.hurl（扩展）

**现有基础上增加:**
```
在 stop 之后、start 之前：
- PATCH /v1/sandboxes/{id}（更新 labels: {"env": "e2e-test"}）→ 200
- GET /v1/sandboxes/{id} → 验证 labels 包含 {"env": "e2e-test"}

在 delete 后：
- GET /v1/sandboxes/{id} → 404（验证删除生效）
```

**新增覆盖:** PATCH 更新 sandbox、删除后 404 验证。

---

### 3.3 P2 — 扩展覆盖（第三轮）

#### 16-cli-auth-flow.hurl（全新）

```
1. POST /v1/auth/cli/flows → 201（创建 CLI 登录流，获取 flow_id + flow_secret）
2. GET /v1/auth/cli/flows/{flow_id}/status（X-Flow-Secret header）→ 200（status: pending）
3. 注册+登录一个用户（获取 session cookie）
4. POST /v1/auth/cli/flows/{flow_id}/approve（session cookie）→ 200（浏览器端批准）
5. GET /v1/auth/cli/flows/{flow_id}/status → 200（status: approved）
6. POST /v1/auth/cli/flows/{flow_id}/exchange（X-Flow-Secret header）→ 200（获取 session_token）
7. GET /v1/auth/user（用 session_token 做 Bearer）→ 200（验证 token 有效）
```

**覆盖:** CLI Auth 全部 6 个端点中的 4 个核心端点（flows, status, approve, exchange）。
浏览器端 `/v1/auth/cli/login` GET/POST 是 HTML 页面，Hurl 可测但价值不大。

#### 17-admin-platform.hurl（全新）

```
1. Admin 登录→创建 API key
2. GET /v1/admin/stats → 200（验证字段存在: total_users, total_sandboxes 等）
3. GET /v1/admin/platform-limits → 200（获取当前限制）
4. PATCH /v1/admin/platform-limits（降低 max_sandboxes 到一个很小的值）→ 200
5. GET /v1/admin/platform-limits → 验证新值生效
6. PATCH /v1/admin/platform-limits（恢复原值）→ 200
7. GET /v1/admin/users/lookup-by-email?email={known_email} → 200
8. POST /v1/admin/users/resolve-emails → 200（批量解析）
9. 注册一个新用户
10. PATCH /v1/auth/users/{user_id}/status（disable）→ 200（禁用用户）
11. POST /v1/auth/login（被禁用用户）→ 401/403（禁用后登录失败）
12. PATCH /v1/auth/users/{user_id}/status（enable）→ 200（启用用户）
13. POST /v1/auth/login（被启用用户）→ 200（启用后登录成功）
```

**覆盖:** admin stats、platform-limits、用户查找、用户禁用/启用。

#### 18-audit-events.hurl（全新）

```
1. Admin 登录
2. 执行一些可审计操作（注册用户、创建 sandbox）
3. GET /v1/audit/filter-options → 200（验证有 actions 列表）
4. GET /v1/audit/events?action=user.register → 200（验证注册事件存在）
5. GET /v1/audit/events?actor_user_id={admin_id} → 200（按用户过滤）
6. 用非 admin 用户：GET /v1/audit/events → 403（权限拒绝）
```

**覆盖:** Audit 全部 2 个端点 + 权限验证。

#### 19-sandbox-patch.hurl（全新）

```
1. 注册→验证→创建 API key
2. 创建 persistent sandbox（需 admin 先 grant storage）
3. 轮询至 READY
4. PATCH /v1/sandboxes/{id}（更新 name, labels, auto_stop_seconds）→ 200
5. GET /v1/sandboxes/{id} → 验证更新生效
6. DELETE /v1/sandboxes/{id} → 204
```

**覆盖:** PATCH sandbox 字段更新。

> **P1 阶段发现:** Kind 集群不支持 VolumeSnapshot CRD，snapshot API 返回 503。
> snapshot 测试不纳入 k8s-e2e（Kind 环境），应作为独立的集成测试在真实 K8s 环境（staging）中运行。
> 文件 19 仅测试 PATCH labels/name/auto_stop_seconds，不包含 snapshot 触发。

---

### 3.4 P3 — 边界和辅助（第四轮）

#### 20-waitlist-support.hurl（全新）

```
1. POST /v1/waitlist → 201（提交 waitlist 申请，无需认证）
2. POST /v1/waitlist（同一 email）→ 409（重复申请）
3. Admin 登录→创建 API key
4. GET /v1/admin/waitlist?status=pending → 200（验证申请出现）
5. PATCH /v1/admin/waitlist/{id}（approve）→ 200
6. POST /v1/support/feedback（session cookie，提交反馈）→ 201
7. GET /v1/admin/support/feedback → 200（验证反馈出现）
```

**覆盖:** Waitlist 提交/管理、Support feedback 提交/查看。

#### 21-error-boundaries.hurl（全新）

集中测试关键错误路径：
```
1. POST /v1/auth/login（错误密码）→ 400（BadRequestError，非 401）
2. POST /v1/auth/login（不存在的邮箱）→ 401
3. GET /v1/auth/user（无认证）→ 401
4. GET /v1/auth/user（畸形 Bearer token）→ 401
5. POST /v1/sandboxes（无认证）→ 401
6. POST /v1/sandboxes（不存在的 template）→ 403
7. GET /v1/sandboxes/nonexistent-id → 404
8. GET /v1/admin/stats（非 admin）→ 403
9. PATCH /v1/admin/platform-limits（非 admin）→ 403
10. POST /v1/auth/register（缺少必填字段）→ 422
```

**覆盖:** 统一验证 401/403/404/422 错误码在关键端点的行为。

---

## 4. 覆盖率对比

| 指标 | 现在 | 目标 | 提升 |
|------|------|------|------|
| 端点覆盖 | ~40/88 (45%) | ~78/88 (89%) | +44% |
| 测试文件 | 10 | 21 | +110% |
| 错误路径覆盖 | ~5 个场景 | ~25 个场景 | 5x |
| Admin 端点覆盖 | 6/19 (32%) | 16/19 (84%) | +52% |
| 全新模块覆盖 | 0 | 4 (CLI/Audit/Waitlist/Support) | +4 |

**仍无法在 E2E 中覆盖的（10 个端点）：**
- OAuth 回调（Google/GitHub）— 需要真实 OAuth provider
- Browser auth（bootstrap/login redirect）— HTML 页面，非 API 验证
- CLI auth 浏览器页面（GET/POST /v1/auth/cli/login）— HTML 页面
- Docs sitemap + doc pages — 静态内容，不含业务逻辑
- WebSocket 代理 — Hurl 不支持 WebSocket 测试
- Auth set-password — 需要 OAuth 注册用户，依赖 OAuth 集成

---

## 5. e2e-test.sh 变量更新

新增文件需要在 `scripts/e2e-test.sh` 中注册变量：

```bash
# 现有 (保留)
email_01="e2e-01-${UNIQUE}@test.treadstone.dev"
email_02="e2e-02-${UNIQUE}@test.treadstone.dev"
# email_03 已在 04 中使用
email_04="e2e-04-${UNIQUE}@test.treadstone.dev"  # 实际对应文件 03
# 05, 06 自行在 hurl 中拼接
email_07="e2e-07-${UNIQUE}@test.treadstone.dev"
email_08="e2e-08-${UNIQUE}@test.treadstone.dev"
email_09="e2e-09-${UNIQUE}@test.treadstone.dev"
email_10="e2e-10-${UNIQUE}@test.treadstone.dev"

# P1 新增 (11-15, 由 dev-claude-opus-46 实现)
email_11="e2e-11-${UNIQUE}@test.treadstone.dev"  # sandbox-lifecycle-ephemeral
email_12="e2e-12-${UNIQUE}@test.treadstone.dev"  # sandbox-lifecycle-persistent
email_13="e2e-13-${UNIQUE}@test.treadstone.dev"  # sandbox-quota-enforcement
email_14="e2e-14-${UNIQUE}@test.treadstone.dev"  # metering-usage-extended
email_15="e2e-15-${UNIQUE}@test.treadstone.dev"  # data-plane-proxy-extended

# P2 新增 (16-19)
email_16="e2e-16-${UNIQUE}@test.treadstone.dev"  # cli-auth-flow
email_17="e2e-17-${UNIQUE}@test.treadstone.dev"  # admin-platform
email_18="e2e-18-${UNIQUE}@test.treadstone.dev"  # audit-events
email_19="e2e-19-${UNIQUE}@test.treadstone.dev"  # sandbox-patch-snapshot

# P3 新增 (20-21)
email_20="e2e-20-${UNIQUE}@test.treadstone.dev"  # waitlist-support
email_21="e2e-21-${UNIQUE}@test.treadstone.dev"  # error-boundaries
```

---

## 6. 执行计划

### 第一轮 PR: P0+P1（文件 01-06 改写 + 11-15 新增）

**改动量:** 3 个改写 + 1 个小改 + 5 个全新 = 9 个文件变更
**预估:** 3-4 天
**分支:** `feature/e2e-improvements`
**状态:** @dev-claude-opus-46 已完成 01-03 + 11-15，待补 06 小改

### 第二轮 PR: P2（文件 16-19）

**改动量:** 4 个全新文件
**预估:** 3-4 天（CLI auth flow 和 snapshot 需要更多调试）
**分支:** `feature/e2e-redesign-p2`

### 第三轮 PR: P3（文件 20-21）

**改动量:** 2 个全新文件
**预估:** 1-2 天
**分支:** `feature/e2e-redesign-p3`

**总工期:** 约 7-10 天（一个开发人员）

---

## 7. 注意事项

1. **并行安全:** 所有文件使用独立 email（前缀必须与文件编号一致，如 `e2e-11-`），无跨文件依赖，可并行执行
2. **Admin 前置:** 文件 04-06, 09-10, 14 需要 admin 操作（验证 token、storage grant），admin 用户通过 `e2e-test.sh` 预注册
3. **K8s 依赖:** 文件 09（proxy）、10（lifecycle）需要真实 K8s 集群，仅在 k8s-e2e CI 中运行。**Snapshot 不在 Kind 环境测试**（无 VolumeSnapshot CRD，返回 503）
4. **Retry 策略:** sandbox 相关操作统一使用 `retry: 90, retry-interval: 2s`（180s 超时），与现有测试一致
5. **向后兼容:** 文件编号保持 01-10 不变，新增 11-21，避免破坏现有 CI 引用
6. **API 行为备注:** 错误密码登录返回 400（`BadRequestError`）而非 401；并发限制错误码为 `concurrent_limit_exceeded`（非 `sandbox_quota_exceeded`）；`GET /v1/auth/user` 响应中验证状态字段名为 `is_verified`（非 `email_verified`，见 `api/auth.py:934`）；register 响应不含 `is_active` 字段
