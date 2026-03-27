# Treadstone Web 设计与 Prompt 完整计划（含 Internal Ops 第二批）

## 摘要

- 设计路线确定为：`Google Stitch 做多版本探索 -> Figma Starter 精修与建立 Design Token / 组件体系 -> Codex 读取 Figma 结构生成代码`。
- 视觉方向默认定为：`高级感基础设施控制台`，`Light-first`，`Slate/Zinc` 中性色底，单一强调色用 `Emerald` 或 `Electric Blue`，禁止紫色 AI 风格、霓虹发光、聊天式伪工作台。
- 产品结构分两批上线：
  - 第一批：`Public Web + User Console`。
  - 第二批：`Internal Ops`，包含 `Admin Metering`、`Audit Events`、`CLI Login Approval`。
- 页面设计必须严格绑定现有真实对象与接口，不发明当前还不存在的功能。依据主要来自 `README.md`、`schemas.py`、`sandboxes.py`、`metering.py`、`audit_event.py`。

## 真实产品边界

### 真实核心对象

- **`User`**：`id`、`email`、`role`、`username`、`is_active`。
- **`Sandbox`**：`id`、`name`、`template`、`status`、`labels`、`auto_stop_interval`、`auto_delete_interval`、`persist`、`storage_size`、`started_at`、`stopped_at`。
- **`SandboxWebLink`**：`web_url`、`open_link`、`expires_at`、`enabled`、`last_used_at`。
- **`ApiKey`**：`id`、`name`、`key_prefix`、`expires_at`、`scope.control_plane`、`scope.data_plane.mode`、`scope.data_plane.sandbox_ids`。
- **`UserPlan / TierTemplate`**：`tier`、月度计算额度、存储额度、并发限制、最长运行时长、允许模板、grace period。
- **`CreditGrant`**：`credit_type`、`grant_type`、`original_amount`、`remaining_amount`、`status`、`expires_at`。
- **`ComputeSession`**：`sandbox_id`、`template`、`credit_rate_per_hour`、`duration_seconds`、`credits_consumed`、`status`。
- **`AuditEvent`**：`action`、`target_type`、`target_id`、`actor_user_id`、`request_id`、`result`、`error_code`、`metadata`。
- **`CliLoginFlow`**：`flow_id`、`status`、`provider`、`expires_at`、`completed_at`。

### 当前真实状态枚举

- **Sandbox**：`creating`、`ready`、`stopped`、`error`、`deleting`。
- **Role**：`admin`、`rw`、`ro`。
- **API Key data plane mode**：`none`、`all`、`selected`。
- **Credit grant status**：`active`、`exhausted`、`expired`。
- **Compute session status**：`active`、`completed`。
- **CLI login flow status**：`pending`、`approved`、`expired`、`used`。

### 明确不做

- Marketplace UI。
- Team / Org 管理。
- 嵌入式 IDE 壳子。
- Billing checkout。
- Chat assistant 面板。
- "在控制台里直接运行代码"的伪 IDE 页面。
- Sandbox 真正的浏览器运行时入口继续是 `Open Web UI / open_link`，控制台只是控制面，不是运行时替代品。

## 页面信息架构

### Public Web

- `/` Landing
- `/pricing` Pricing / Free Tier
- `/quickstart` Quickstart / Docs Entry
- `/auth/sign-in` Sign in
- `/auth/sign-up` Register

### User Console

- `/app` Dashboard
- `/app/templates` Templates
- `/app/sandboxes` Sandboxes List
- `/app/sandboxes/new` Create Sandbox
- `/app/sandboxes/:id` Sandbox Detail
- `/app/api-keys` API Keys
- `/app/usage` Usage & Credits
- `/app/settings` Account Settings

### Internal Ops 第二批

- `/internal/admin/metering` Admin Metering
- `/internal/audit` Audit Events
- `/auth/cli/login?flow_id=...` CLI Login Approval / Success Flow

## 每个页面必须承载的功能

| 页面 | 功能要点 |
|------|--------|
| **Landing** | 产品定位、核心能力、CLI/SDK/API/Web Console 四条入口、模板规格预览、浏览器 hand-off 说明、Start free CTA。 |
| **Pricing / Free Tier** | 明确 Free 的 `10 vCPU-hours / month`、`50 vCPU-hours welcome bonus`、`max_concurrent_running = 1`、`max_sandbox_duration_seconds = 1800`、`storage = 0 GiB`；展示 Pro / Ultra 作为可信升级路径。 |
| **Quickstart** | 安装 CLI、创建 API Key、创建第一个 Sandbox、打开 Web UI、切到 SDK/API。 |
| **Sign in / Register** | 邮箱登录为主，按 `/v1/config` 动态支持 Google / GitHub。 |
| **Dashboard** | 当前 tier、剩余额度、welcome bonus、最近 sandboxes、模板快捷入口、API key onboarding、最近 hand-off 入口。 |
| **Templates** | 内置规格卡片或表格，突出 `tiny / small / medium / large / xlarge` 的 CPU、内存、适用场景。 |
| **Sandboxes** | 列表、筛选、状态 badge、Start/Stop/Delete/Open Web UI/Copy proxy URL/Copy sandbox ID。 |
| **Create Sandbox** | 模板选择、可选名称、labels、auto stop、auto delete、persist、storage size、校验规则。 |
| **Sandbox Detail** | 状态、template、ID、labels、runtime 时间、persist/storage、proxy URL、web link 状态、创建/撤销 hand-off。 |
| **API Keys** | 创建、一次性展示 secret、复制、过期时间、scope、selected sandbox 绑定、删除。 |
| **Usage & Credits** | Overview、Sessions、Grants、Plan Details 四块，突出免费额度与剩余额度。 |
| **Account Settings** | email、role、password change、logout。 |
| **Admin Metering** | tier templates、user usage、plan override、single grant、batch grants。 |
| **Audit Events** | 按 `action / target_type / target_id / actor_user_id / request_id / result / since / until` 过滤查看。 |
| **CLI Login Approval** | 展示 `flow_id`、登录方式、过期状态、成功页，强调"你可以关闭这个页面并返回终端"。 |

## 核心组件与按钮库

### 全局组件

- `PrimaryButton`、`SecondaryButton`、`GhostButton`、`DestructiveButton`、`CopyButton`、`SplitActionButton`。
- `StatusBadge`、`UsageMeter`、`CreditBar`、`StatTile`、`KeyValueList`、`CodeBlockWithCopy`、`ActivityFeed`、`DataTable`、`EmptyState`、`DangerModal`、`Toast`、`Skeleton`。

### 关键按钮动作

| 页面 | 主要按钮动作 |
|------|------------|
| **Dashboard** | `Create Sandbox`、`Create API Key`、`View Usage`、`Open Latest Sandbox`。 |
| **Sandboxes** | `Start`、`Stop`、`Open Web UI`、`Copy Proxy URL`、`Copy Sandbox ID`、`Delete`。 |
| **Sandbox Detail** | `Create/Recreate Web Link`、`Disable Web Link`、`Open Web UI`。 |
| **API Keys** | `Create Key`、`Copy Secret`、`Rename`、`Update Scope`、`Set Expiry`、`Clear Expiry`、`Delete`。 |
| **Usage** | `Filter Active`、`Filter Completed`、`Upgrade`。 |
| **Admin Metering** | `Update Tier Template`、`Apply To Existing Users`、`Change User Tier`、`Grant Credits`、`Batch Grant`。 |
| **Audit** | `Apply Filters`、`Reset Filters`、`Copy Request ID`。 |
| **CLI Login** | `Continue with Email`、`Continue with Google`、`Continue with GitHub`、`Close Window` 提示成功态。 |

## Stitch 使用顺序

1. **第 1 步**：只跑 `Dashboard` 5 个视觉变体，20 分钟内选定整体视觉方向。
2. **第 2 步**：用选中的风格继续生成 `Landing`、`Sandboxes`、`Sandbox Detail`、`Usage` 四个关键页，验证这个视觉系统能否同时承载营销、管理、数据和操作。
3. **第 3 步**：补齐剩余页面，再导出 Figma。
4. **第 4 步**：在 Figma 中统一命名与 Token：
   - **颜色**：`color.bg.*`、`color.surface.*`、`color.text.*`、`color.accent.*`、`color.success.*`、`color.warning.*`、`color.danger.*`。
   - **间距**：`space.2/4/8/12/16/24/32/40/48`。
   - **圆角**：`radius.sm/md/lg/xl/2xl`。
   - **阴影**：`shadow.surface`、`shadow.popover`、`shadow.focus`。
   - **组件**：`Button/Primary`、`Button/Secondary`、`Badge/Status`、`Table/Row`、`Card/Metric`、`Form/Input`。
5. **第 5 步**：Codex 只读取整理后的主 Figma 文件，不读取未整理草稿。Starter 的 MCP 调用额度低，保持一个干净主文件即可。

## Stitch 全局总提示词

```
Design a premium light-first web experience for Treadstone, an agent-native sandbox platform for AI agents and developers. This is a technical B2B control plane, not a consumer AI app. The product already supports account registration, sign-in, optional Google and GitHub login, API key management, sandbox template listing, sandbox create/list/detail/start/stop/delete, browser hand-off links, usage and credit tracking, admin metering, audit events, and browser-based CLI login approval. The UI must reflect real existing objects and fields only: User, Sandbox, SandboxWebLink, ApiKey, UserPlan, TierTemplate, CreditGrant, ComputeSession, AuditEvent, and CliLoginFlow. Do not invent marketplace, team collaboration, embedded IDE shell, billing checkout, chat assistant, or runtime code editor features. Use neutral zinc/slate surfaces with one emerald or electric-blue accent, premium typography, strong status visibility, elegant tables, clear empty states, and explicit operational hierarchy. No purple AI aesthetic, no neon glow, no playful cartoon illustrations.
```

## Dashboard 视觉探索 Prompt

### Variant A

```
Using the Treadstone master brief, design a dashboard that feels like a premium cloud infrastructure console. Prioritize sandbox status, usage limits, recent activity, and operational actions. Include current tier, billing period, compute remaining, welcome bonus, recent sandboxes, template quick actions, and a strong Create Sandbox CTA.
```

### Variant B

```
Using the Treadstone master brief, design a dashboard focused on the first-run workflow: create account, create API key, create first sandbox, open Web UI, continue in CLI or SDK. Make the onboarding path visible without feeling tutorial-heavy.
```

### Variant C

```
Using the Treadstone master brief, design a dashboard where free-tier clarity is the first priority. Make 10 vCPU-hours monthly, 50 vCPU-hours welcome bonus, 1 max concurrent sandbox, and 1800-second max duration immediately legible.
```

### Variant D

```
Using the Treadstone master brief, design a minimal technical dashboard with more whitespace, sharper typography, fewer boxed cards, and stronger use of dividers and status chips. It should feel closer to a serious developer platform than a generic analytics template.
```

### Variant E

```
Using the Treadstone master brief, design a trust-first dashboard that emphasizes API key safety, browser hand-off control, recent audit-like activity, and account-level visibility. The page should feel secure, production-minded, and calm.
```

## 第一批页面 Prompt 清单

### 1. Landing

```
Design the public landing page for Treadstone. Explain that it is an agent-native sandbox platform for AI agents and developers, focused on isolated environments, lifecycle control, API keys, browser hand-off, and open deployment. Include a split hero, workflow section, CLI / SDK / API / Web Console entry section, built-in sandbox tier preview, browser hand-off explanation, and trust section. Primary CTA: Start free. Secondary CTAs: Read docs and Install CLI.
```

### 2. Pricing / Free Tier

```
Design a pricing page for Treadstone. Free is the primary live plan and must clearly show 10 vCPU-hours monthly, 50 vCPU-hours welcome bonus, max 1 concurrent running sandbox, max sandbox duration 1800 seconds, and no storage credits. Pro and Ultra should be shown as credible higher tiers with more compute, storage, concurrency, and duration. Use a technical comparison table, not fluffy marketing cards.
```

### 3. Quickstart / Docs Entry

```
Design a quickstart page for developers evaluating Treadstone. Show three entry paths: CLI, Python SDK / API, and Web console. Include a copyable CLI install command, steps for register or sign in, create API key, list templates, create sandbox, and open browser hand-off. Make it feel like a docs landing page with structured code snippets and action links.
```

### 4. Sign in

```
Design a Treadstone sign-in page. Email and password are the primary path. Google and GitHub buttons should appear as optional providers when enabled. Show clear error handling, a technical but polished layout, and supporting copy that this account manages sandboxes, API keys, usage credits, and browser hand-off links.
```

### 5. Register

```
Design a Treadstone create-account page. Keep it minimal and trustworthy. Include email, password, submit, optional Google and GitHub sign-up paths, and a short note that new users start on the free tier with visible compute limits and welcome bonus credits.
```

### 6. Dashboard

```
Design the main logged-in dashboard for Treadstone. Show current tier, billing period, compute used and remaining, welcome bonus credits, current running count, recent sandboxes, quick template launcher, and API key readiness. Primary CTA: Create Sandbox. Secondary actions: Create API Key, View Usage, Open Latest Sandbox. Include meaningful empty states for a brand new account.
```

### 7. Templates

```
Design the templates catalog page for Treadstone. Show built-in sandbox templates with display name, CPU, memory, description, and ideal use case. Recommended tiers to surface: tiny, small, medium, large, xlarge. Every template needs a clear Use Template action that leads into sandbox creation.
```

### 8. Sandboxes

```
Design the sandboxes list page for Treadstone as a premium data table. Columns should include sandbox name, template, status, persistent or ephemeral mode, storage size, created at, and browser availability. Include row actions for Start, Stop, Open Web UI, Copy Proxy URL, Copy Sandbox ID, and Delete. Add loading, empty, and destructive confirmation states.
```

### 9. Create Sandbox

```
Design the create sandbox flow for Treadstone. Fields: template selector, optional sandbox name, labels, auto stop interval in minutes, auto delete interval in minutes, persist toggle, and storage size when persist is enabled. Show inline validation that sandbox names must be lowercase letters, numbers, or hyphens, 1 to 55 characters, unique per current user, and storage size is only allowed when persist is enabled. Add a side panel explaining what the configuration means for a free-tier user.
```

### 10. Sandbox Detail

```
Design the sandbox detail page for Treadstone. Header should show sandbox name, status, template, and actions: Start, Stop, Open Web UI, Create or Recreate Web Link, Disable Web Link, and Delete. Body should show sandbox ID, template, labels, created at, started at, stopped at, persistent storage details, proxy URL, browser web URL, open link expiry, and last used time. This is a control-plane page only, not an embedded IDE.
```

### 11. API Keys

```
Design the API keys page for Treadstone. Show key name, prefix preview, created time, updated time, expiry, and scope. Include a create-key modal with name, optional expiration, control-plane access, and data-plane scope mode of none, all, or selected sandbox IDs. After creation, show the full secret once with a strong copy action and a warning that it will not be shown again.
```

### 12. Usage & Credits

```
Design the usage page for Treadstone. Show current tier, billing period, monthly compute limit, monthly used, monthly remaining, extra remaining credits, total remaining credits, storage quota, current running sandboxes, max concurrent running, and max sandbox duration. Add four clear sections or tabs: Overview, Compute Sessions, Credit Grants, and Plan Details. Make the free-tier story extremely legible and trustworthy.
```

### 13. Account Settings

```
Design the account settings page for Treadstone. Show email, role, active status, password change form, and sign-out action. Keep the page restrained and operational, with security-oriented tone rather than lifestyle-product styling.
```

## 第二批 Internal Ops Prompt 清单

### 1. Admin Metering

```
Design an internal admin metering console for Treadstone. It should manage tier templates, inspect a user's usage, change a user's plan tier, apply plan overrides, issue single-user credit grants, and run batch credit grants. Surface real fields such as compute credits monthly, storage credits monthly, max concurrent running, max sandbox duration seconds, allowed templates, grace period seconds, original amount, remaining amount, grant type, campaign id, and expires at. The UI must feel like a serious internal operations tool with safe defaults and explicit confirmation for bulk actions.
```

### 2. Audit Events

```
Design an internal audit events page for Treadstone admins. Show a structured event table with filters for action, target type, target id, actor user id, request id, result, since, and until. Table columns should include created time, action, target, actor, credential type, result, request id, and metadata preview. Make it easy to scan incidents, copy request IDs, and inspect metadata without turning the page into a cluttered SIEM clone.
```

### 3. CLI Login Approval

```
Design a standalone browser page for Treadstone CLI login approval. It should support a pending login flow identified by flow_id, email sign-in, optional Google and GitHub sign-in, inline invalid-password errors, expired or already-used states, and a success screen that clearly tells the user they can close the window and return to the terminal. Keep it compact, secure, and aligned with the main product's visual system.
```

## Figma 结构化整理要求

### 页面命名统一

- `Public/Landing`
- `Public/Pricing`
- `Public/Quickstart`
- `Auth/SignIn`
- `Auth/Register`
- `App/Dashboard`
- `App/Templates`
- `App/Sandboxes`
- `App/CreateSandbox`
- `App/SandboxDetail`
- `App/ApiKeys`
- `App/Usage`
- `App/Settings`
- `Internal/AdminMetering`
- `Internal/AuditEvents`
- `Auth/CliLogin`

### 组件命名统一

- `Button/Primary`
- `Button/Secondary`
- `Button/Destructive`
- `Badge/Status/Sandbox`
- `Badge/Status/Grant`
- `Table/Sandboxes`
- `Table/ApiKeys`
- `Table/AuditEvents`
- `Card/Metric`
- `Card/Usage`
- `Form/Input/Text`
- `Form/Input/Email`
- `Form/Input/Password`
- `Form/Select`
- `Form/Toggle`
- `Modal/ConfirmDanger`

### Token 命名统一后执行

Token 命名统一后，再让 Codex 用 Figma MCP 读主文件生成代码，不从 Stitch 粗稿直接生成。

## 验收标准

- 用户第一次打开官网时，能在 30 秒内理解 Treadstone 是什么、适合谁、Free Tier 给什么。
- 用户第一次进入控制台时，能在不看命令行的情况下完成：创建账户、看见额度、创建第一个 Sandbox、打开 Web UI、创建 API Key。
- 所有数据页都有完整的 `loading / empty / validation error / destructive confirmation / success feedback`。
- `Sandbox`、`ApiKey`、`Usage`、`Admin Metering`、`Audit` 页面都能直接映射到真实接口字段与数据库对象，不需要设计师或实现者二次猜字段。
- 第二批 Internal Ops 页面与主产品视觉系统一致，但信息密度更高、容错更强、确认动作更明确。

## Assumptions

- 实现阶段仍以现有 API 为准：`/v1/config`、`/v1/auth/*`、`/v1/auth/cli/*`、`/v1/sandbox-templates`、`/v1/sandboxes*`、`/v1/usage*`、`/v1/admin/*`、`/v1/audit/events`。
- Pricing 页面中的 Free / Pro / Ultra 展示，以当前测试与模型中已有额度和限制为准，不扩展到 Stripe checkout。
- 外部工具策略固定为：`Stitch` 做探索，`Figma` 做结构化收口，`Codex` 做实现；`Paper` 暂不作为主流程。
- 工具可用性参考官方资料：
  - [Google Stitch announcement](https://developers.googleblog.com/stitch-a-new-way-to-design-uis/)
  - [Figma MCP guide](https://help.figma.com/hc/en-us/articles/32132100833559-Guide-to-the-Figma-MCP-server)
  - [Figma MCP troubleshooting](https://developers.figma.com/docs/figma-mcp-server/tools-not-loading/)
  - [Figma rate limits](https://help.figma.com/hc/en-us/articles/34963238552855-What-if-I-m-rate-limited)
  - [Paper MCP docs](https://paper.design/docs/mcp)
