# Treadstone Web 设计与 Prompt 完整计划（Neon / Resend 风格版）

## 摘要

- 设计路线保持不变：`Google Stitch 做多版本探索 -> Figma Starter 精修与建立 Design Token / 组件体系 -> Codex 读取 Figma 结构生成代码`。
- 本版把整体风格从“高级感 light-first SaaS”调整为：`Neon / Resend 式极简、平面、克制、工程化控制台`。
- 视觉方向默认定为：`Dark-first`，近黑色背景，低对比中性色表面，细边框，极少阴影，少装饰，多留白，强调表格、工具栏、筛选栏、列表与状态。
- 产品结构仍分两批上线：
  - 第一批：`Public Web + User Console`
  - 第二批：`Internal Ops`，包含 `Admin Metering`、`Audit Events`、`CLI Login Approval`
- 页面设计必须严格绑定现有真实对象与接口，不发明当前还不存在的功能。依据主要来自 `README.md`、`schemas.py`、`sandboxes.py`、`metering.py`、`audit_event.py`、`cli_login_flow.py`。

## 视觉总纲

### 风格参考

- 参考方向：Neon Console、Resend Dashboard。
- 目标气质：像一个真实在运营的开发者平台，而不是一套 AI 生成的通用 SaaS 模板。
- 设计关键词：`flat`、`minimal`、`technical`、`quiet`、`dense but breathable`、`dark neutral`、`clear hierarchy`。

### 核心视觉原则

- **深色优先**：主背景接近黑色或深炭灰，避免大面积纯蓝紫。
- **平面而非华丽**：禁止玻璃拟态、霓虹描边、渐变发光、漂浮卡片雨、营销型插画。
- **边框优先于阴影**：用 `1px` 边框和分割线建立层次，阴影极弱或完全不用。
- **表格优先于卡片**：数据密集页面优先使用表格、列表、工具栏、内联指标，而不是大量营销感卡片。
- **空状态克制**：空状态要像 Resend 那样安静、中心对齐、文案短、CTA 明确。
- **状态比装饰重要**：颜色主要用于 `status`、`warning`、`danger`、`link`，不是用于氛围。
- **排版偏工程化**：标题有力但不过分夸张；正文尺寸克制；ID、命令、额度和 URL 明确使用等宽字体。
- **动作区像工具栏**：按钮不做夸张动画，优先做明确、紧凑、好扫描的主次关系。

### 禁止项

- 禁止 Bento、Apple 式漂浮大卡、营销式 3D 图形。
- 禁止大面积玻璃态、模糊背景、彩色 mesh gradient。
- 禁止过多圆角和厚重阴影。
- 禁止“AI 紫 / 霓虹蓝”主色。
- 禁止把控制台做成伪聊天产品或伪 IDE。

## 真实产品边界

### 真实核心对象

- **`User`**：`id`、`email`、`role`、`username`、`is_active`
- **`Sandbox`**：`id`、`name`、`template`、`status`、`labels`、`auto_stop_interval`、`auto_delete_interval`、`persist`、`storage_size`、`started_at`、`stopped_at`
- **`SandboxWebLink`**：`web_url`、`open_link`、`expires_at`、`enabled`、`last_used_at`
- **`ApiKey`**：`id`、`name`、`key_prefix`、`expires_at`、`scope.control_plane`、`scope.data_plane.mode`、`scope.data_plane.sandbox_ids`
- **`UserPlan / TierTemplate`**：`tier`、月度计算额度、存储额度、并发限制、最长运行时长、允许模板、`grace_period_seconds`
- **`CreditGrant`**：`credit_type`、`grant_type`、`original_amount`、`remaining_amount`、`status`、`expires_at`
- **`ComputeSession`**：`sandbox_id`、`template`、`credit_rate_per_hour`、`duration_seconds`、`credits_consumed`、`status`
- **`AuditEvent`**：`action`、`target_type`、`target_id`、`actor_user_id`、`request_id`、`result`、`error_code`、`metadata`
- **`CliLoginFlow`**：`flow_id`、`status`、`provider`、`expires_at`、`completed_at`

### 当前真实状态枚举

- **Sandbox**：`creating`、`ready`、`stopped`、`error`、`deleting`
- **Role**：`admin`、`rw`、`ro`
- **API Key data plane mode**：`none`、`all`、`selected`
- **Credit grant status**：`active`、`exhausted`、`expired`
- **Compute session status**：`active`、`completed`
- **CLI login flow status**：`pending`、`approved`、`expired`、`used`

### 明确不做

- Marketplace UI
- Team / Org 管理
- 嵌入式 IDE 壳子
- Billing checkout
- Chat assistant 面板
- “在控制台里直接运行代码”的伪 IDE 页面
- Sandbox 真正的浏览器运行时入口继续是 `Open Web UI / open_link`，控制台只是控制面，不是运行时替代品

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
| **Landing** | 产品定位、核心能力、CLI/SDK/API/Web Console 四条入口、模板规格预览、浏览器 hand-off 说明、Start free CTA |
| **Pricing / Free Tier** | 明确 Free 的 `10 vCPU-hours / month`、`50 vCPU-hours welcome bonus`、`max_concurrent_running = 1`、`max_sandbox_duration_seconds = 1800`、`storage = 0 GiB`，展示 Pro / Ultra 作为可信升级路径 |
| **Quickstart** | 安装 CLI、创建 API Key、创建第一个 Sandbox、打开 Web UI、切到 SDK/API |
| **Sign in / Register** | 邮箱登录为主，按 `/v1/config` 动态支持 Google / GitHub |
| **Dashboard** | 当前 tier、剩余额度、welcome bonus、最近 sandboxes、模板快捷入口、API key onboarding、最近 hand-off 入口 |
| **Templates** | 内置规格表格或精简列表，突出 `tiny / small / medium / large / xlarge` 的 CPU、内存、适用场景 |
| **Sandboxes** | 列表、筛选、状态 badge、Start/Stop/Delete/Open Web UI/Copy proxy URL/Copy sandbox ID |
| **Create Sandbox** | 模板选择、可选名称、labels、auto stop、auto delete、persist、storage size、校验规则 |
| **Sandbox Detail** | 状态、template、ID、labels、runtime 时间、persist/storage、proxy URL、web link 状态、创建/撤销 hand-off |
| **API Keys** | 创建、一次性展示 secret、复制、过期时间、scope、selected sandbox 绑定、删除 |
| **Usage & Credits** | Overview、Sessions、Grants、Plan Details 四块，突出免费额度与剩余额度 |
| **Account Settings** | email、role、password change、logout |
| **Admin Metering** | tier templates、user usage、plan override、single grant、batch grants |
| **Audit Events** | 按 `action / target_type / target_id / actor_user_id / request_id / result / since / until` 过滤查看 |
| **CLI Login Approval** | 展示 `flow_id`、登录方式、过期状态、成功页，强调“你可以关闭这个页面并返回终端” |

## 组件原则与按钮体系

### 页面骨架原则

- 左侧导航 + 顶部工具条是默认控制台布局。
- 内容区以 `Section header + Toolbar + Table/List/Detail blocks` 组成。
- 页面优先使用：
  - `Sidebar`
  - `Topbar`
  - `SectionHeader`
  - `Toolbar`
  - `FilterBar`
  - `InlineStat`
  - `DataTable`
  - `DetailList`
  - `EmptyState`

### 全局组件

- `PrimaryButton`
- `SecondaryButton`
- `GhostButton`
- `DestructiveButton`
- `CopyButton`
- `StatusBadge`
- `ToolbarSearch`
- `ToolbarSelect`
- `InlineStat`
- `UsageMeter`
- `CreditBar`
- `KeyValueList`
- `CodeBlockWithCopy`
- `DataTable`
- `EmptyState`
- `DangerModal`
- `Toast`
- `Skeleton`

### 关键按钮动作

| 页面 | 主要按钮动作 |
|------|------------|
| **Dashboard** | `Create Sandbox`、`Create API Key`、`View Usage`、`Open Latest Sandbox` |
| **Sandboxes** | `Start`、`Stop`、`Open Web UI`、`Copy Proxy URL`、`Copy Sandbox ID`、`Delete` |
| **Sandbox Detail** | `Create/Recreate Web Link`、`Disable Web Link`、`Open Web UI` |
| **API Keys** | `Create Key`、`Copy Secret`、`Rename`、`Update Scope`、`Set Expiry`、`Clear Expiry`、`Delete` |
| **Usage** | `Filter Active`、`Filter Completed`、`Upgrade` |
| **Admin Metering** | `Update Tier Template`、`Apply To Existing Users`、`Change User Tier`、`Grant Credits`、`Batch Grant` |
| **Audit** | `Apply Filters`、`Reset Filters`、`Copy Request ID` |
| **CLI Login** | `Continue with Email`、`Continue with Google`、`Continue with GitHub`、成功态关闭提示 |

## Stitch 使用顺序

1. **先跑 Dashboard 视觉探索**：只做 5 个变体，20 分钟内定方向。
2. **验证系统适配性**：继续生成 `Landing`、`Sandboxes`、`Sandbox Detail`、`Usage` 四个关键页。
3. **补齐所有页面**：在同一风格下补 `Templates`、`API Keys`、`Settings`、第二批 Internal Ops。
4. **导入 Figma 并统一整理**：
   - 风格统一
   - 组件命名统一
   - Token 命名统一
   - 删除探索稿中的噪音样式
5. **Codex 只读整理后的主文件**，不读取探索中的分支页面。

## Prompt 使用说明

- 为了让 Stitch 更稳定，以下 prompt 保持英文。
- 所有 prompt 都已经内置：
  - Treadstone 真实功能边界
  - Neon / Resend 风格约束
  - 深色、平面、克制的排版与布局要求
- 使用时不要再额外加 “make it more premium” 这类含糊描述，否则会把结果拉回通用 SaaS 模板。

## Stitch 全局总提示词

```text
Design a dark-first, flat, minimal web experience for Treadstone, an agent-native sandbox platform for AI agents and developers. The visual style should be closer to Neon Console or Resend Dashboard than to a generic glossy SaaS template. This is a technical B2B control plane, not a consumer AI app. The product already supports account registration, sign-in, optional Google and GitHub login, API key management, sandbox template listing, sandbox create/list/detail/start/stop/delete, browser hand-off links, usage and credit tracking, admin metering, audit events, and browser-based CLI login approval. The UI must reflect real existing objects and fields only: User, Sandbox, SandboxWebLink, ApiKey, UserPlan, TierTemplate, CreditGrant, ComputeSession, AuditEvent, and CliLoginFlow. Do not invent marketplace, team collaboration, embedded IDE shell, billing checkout, chat assistant, or runtime code editor features. Use near-black backgrounds, subtle neutral surfaces, thin borders, minimal shadows, restrained typography, elegant dense tables, quiet empty states, simple toolbars, and clear operational hierarchy. Avoid gradients, glassmorphism, bento layouts, purple AI aesthetics, glowing effects, playful illustrations, and over-designed hero sections.
```

## Dashboard 视觉探索 Prompt

### Variant A：Neon 式项目控制台

```text
Using the Treadstone master brief, design a dashboard inspired by the structural clarity of Neon Console. Use a left sidebar, a restrained top toolbar, a large page title, compact inline usage metrics, and a strong operational table or list. Prioritize sandbox status, current tier, compute remaining, welcome bonus, recent sandboxes, and one primary Create Sandbox action. Keep the page flat, dark, and quietly technical.
```

### Variant B：Resend 式极简空状态

```text
Using the Treadstone master brief, design a dashboard with the calm minimalism of Resend. Favor quiet spacing, clean empty states, low-noise surfaces, and simple action hierarchy. The page should work especially well for a brand new user who has no sandboxes yet. Include onboarding actions for Create Sandbox, Create API Key, and View Usage.
```

### Variant C：额度与限制优先

```text
Using the Treadstone master brief, design a dashboard where free-tier clarity is the first priority. Make 10 vCPU-hours monthly, 50 vCPU-hours welcome bonus, 1 max concurrent sandbox, and 1800-second max duration immediately understandable. Present the information as restrained inline stats and progress indicators, not marketing cards.
```

### Variant D：数据表驱动的运营台

```text
Using the Treadstone master brief, design a dashboard that feels like an internal operations console. Use more tables and list rows, fewer decorative sections, and stronger toolbar patterns. Include recent sandboxes, latest web links, recent API key activity, and compact usage indicators. The page should feel utilitarian in a polished way.
```

### Variant E：信任与控制优先

```text
Using the Treadstone master brief, design a dashboard that emphasizes operational trust: browser hand-off control, API key visibility, usage limits, and recent audit-like activity. Keep it visually restrained, dark, and flat. Avoid decorative cards and use compact structured sections instead.
```

## 第一批页面 Prompt 清单

### 1. Landing

```text
Design the public landing page for Treadstone in a dark, minimal, flat product style inspired by Neon and Resend. Explain that Treadstone is an agent-native sandbox platform for AI agents and developers, focused on isolated environments, lifecycle control, API keys, browser hand-off, and open deployment. Avoid glossy marketing visuals. Use a restrained hero, a product workflow section, a CLI / SDK / API / Web Console entry section, built-in sandbox tier preview, browser hand-off explanation, and a trust section. Primary CTA: Start free. Secondary CTAs: Read docs and Install CLI.
```

### 2. Pricing / Free Tier

```text
Design a pricing page for Treadstone in the same dark, minimal style. Free is the primary live plan and must clearly show 10 vCPU-hours monthly, 50 vCPU-hours welcome bonus, max 1 concurrent running sandbox, max sandbox duration 1800 seconds, and no storage credits. Pro and Ultra should be shown as credible higher tiers with more compute, storage, concurrency, and duration. Use a technical comparison table and restrained typography, not fluffy pricing cards.
```

### 3. Quickstart / Docs Entry

```text
Design a quickstart page for developers evaluating Treadstone. The page should feel like a product docs entry inside a dark technical platform, not a blog. Show three entry paths: CLI, Python SDK / API, and Web console. Include a copyable CLI install command, steps for register or sign in, create API key, list templates, create sandbox, and open browser hand-off. Use clean code blocks, toolbars, and section dividers.
```

### 4. Sign in

```text
Design a Treadstone sign-in page with a dark, flat, minimal interface. Email and password are the primary path. Google and GitHub buttons should appear as optional providers when enabled. Show clear error handling and supporting copy that this account manages sandboxes, API keys, usage credits, and browser hand-off links. The page should feel closer to a serious developer tool than a consumer login form.
```

### 5. Register

```text
Design a Treadstone create-account page in the same dark, flat style. Include email, password, submit, optional Google and GitHub sign-up paths, and a short note that new users start on the free tier with visible compute limits and welcome bonus credits. Keep the layout minimal and trustworthy.
```

### 6. Dashboard

```text
Design the main logged-in dashboard for Treadstone as a dark, flat technical control plane. Show current tier, billing period, compute used and remaining, welcome bonus credits, current running count, recent sandboxes, quick template launcher, and API key readiness. Primary CTA: Create Sandbox. Secondary actions: Create API Key, View Usage, Open Latest Sandbox. Use concise section headers, inline stats, and a restrained empty state for a brand new account.
```

### 7. Templates

```text
Design the templates catalog page for Treadstone. Use a dark technical layout with a toolbar and either a compact data table or a restrained list. Show built-in sandbox templates with display name, CPU, memory, description, and ideal use case. Recommended tiers to surface: tiny, small, medium, large, xlarge. Every template needs a clear Use Template action that leads into sandbox creation.
```

### 8. Sandboxes

```text
Design the sandboxes list page for Treadstone as a dark, flat, high-clarity data table page. Use a left navigation shell, a page header, a compact filter/search toolbar, and a primary Create Sandbox button. Columns should include sandbox name, template, status, persistent or ephemeral mode, storage size, created at, and browser availability. Include row actions for Start, Stop, Open Web UI, Copy Proxy URL, Copy Sandbox ID, and Delete. Add loading, empty, and destructive confirmation states in a quiet Resend-like tone.
```

### 9. Create Sandbox

```text
Design the create sandbox flow for Treadstone as a focused dark technical form. Fields: template selector, optional sandbox name, labels, auto stop interval in minutes, auto delete interval in minutes, persist toggle, and storage size when persist is enabled. Show inline validation that sandbox names must be lowercase letters, numbers, or hyphens, 1 to 55 characters, unique per current user, and storage size is only allowed when persist is enabled. Present the form in a clean flat layout with a slim side summary for free-tier implications.
```

### 10. Sandbox Detail

```text
Design the sandbox detail page for Treadstone as a dark, flat operational detail view. Header should show sandbox name, status, template, and actions: Start, Stop, Open Web UI, Create or Recreate Web Link, Disable Web Link, and Delete. Body should show sandbox ID, template, labels, created at, started at, stopped at, persistent storage details, proxy URL, browser web URL, open link expiry, and last used time. Use key-value blocks, subtle section borders, and compact action placement. This is a control-plane page only, not an embedded IDE.
```

### 11. API Keys

```text
Design the API keys page for Treadstone in a dark minimal control-plane style. Show key name, prefix preview, created time, updated time, expiry, and scope. Include a create-key modal with name, optional expiration, control-plane access, and data-plane scope mode of none, all, or selected sandbox IDs. After creation, show the full secret once with a strong copy action and a warning that it will not be shown again. Prefer a table and a compact modal over large cards.
```

### 12. Usage & Credits

```text
Design the usage page for Treadstone as a dark, flat usage console. Show current tier, billing period, monthly compute limit, monthly used, monthly remaining, extra remaining credits, total remaining credits, storage quota, current running sandboxes, max concurrent running, and max sandbox duration. Add four clear sections or tabs: Overview, Compute Sessions, Credit Grants, and Plan Details. The page should feel explicit, calm, and highly legible, especially for free-tier users watching their limits.
```

### 13. Account Settings

```text
Design the account settings page for Treadstone with a restrained dark technical style. Show email, role, active status, password change form, and sign-out action. Keep the page quiet, compact, and security-oriented, with simple section dividers and flat form styling.
```

## 第二批 Internal Ops Prompt 清单

### 1. Admin Metering

```text
Design an internal admin metering console for Treadstone in a dark, flat operations style. It should manage tier templates, inspect a user's usage, change a user's plan tier, apply plan overrides, issue single-user credit grants, and run batch credit grants. Surface real fields such as compute credits monthly, storage credits monthly, max concurrent running, max sandbox duration seconds, allowed templates, grace period seconds, original amount, remaining amount, grant type, campaign id, and expires at. The UI must feel like a serious internal tool with safe defaults, obvious destructive boundaries, and explicit confirmation for bulk actions.
```

### 2. Audit Events

```text
Design an internal audit events page for Treadstone admins in a dark minimal operations style. Show a structured event table with filters for action, target type, target id, actor user id, request id, result, since, and until. Table columns should include created time, action, target, actor, credential type, result, request id, and metadata preview. Make it easy to scan incidents, copy request IDs, and inspect metadata without turning the page into a cluttered SIEM clone.
```

### 3. CLI Login Approval

```text
Design a standalone browser page for Treadstone CLI login approval in the same dark, flat visual system. It should support a pending login flow identified by flow_id, email sign-in, optional Google and GitHub sign-in, inline invalid-password errors, expired or already-used states, and a success screen that clearly tells the user they can close the window and return to the terminal. Keep it compact, quiet, and highly trustworthy.
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

- `Layout/Sidebar`
- `Layout/Topbar`
- `Layout/Toolbar`
- `Button/Primary`
- `Button/Secondary`
- `Button/Ghost`
- `Button/Destructive`
- `Badge/Status/Sandbox`
- `Badge/Status/Grant`
- `Table/Sandboxes`
- `Table/ApiKeys`
- `Table/AuditEvents`
- `Stat/Inline`
- `Surface/Section`
- `Form/Input/Text`
- `Form/Input/Email`
- `Form/Input/Password`
- `Form/Select`
- `Form/Toggle`
- `Modal/ConfirmDanger`
- `State/Empty`

### Token 命名建议

- **颜色**
  - `color.bg.canvas`
  - `color.bg.sidebar`
  - `color.bg.surface`
  - `color.bg.surface-muted`
  - `color.border.default`
  - `color.border.subtle`
  - `color.text.primary`
  - `color.text.secondary`
  - `color.text.muted`
  - `color.link.default`
  - `color.success.default`
  - `color.warning.default`
  - `color.danger.default`
- **间距**
  - `space.2`
  - `space.4`
  - `space.8`
  - `space.12`
  - `space.16`
  - `space.20`
  - `space.24`
  - `space.32`
- **圆角**
  - `radius.sm`
  - `radius.md`
  - `radius.lg`
- **阴影**
  - `shadow.none`
  - `shadow.subtle`

### Token 使用约束

- 深色主题下优先通过背景层级和边框建立结构，不依赖阴影。
- 控件半径控制在小到中等范围，不做圆润消费品风格。
- 强调色主要用于链接、焦点、激活状态和成功状态。

## 验收标准

- 用户第一次打开官网时，能在 30 秒内理解 Treadstone 是什么、适合谁、Free Tier 给什么。
- 用户第一次进入控制台时，能在不看命令行的情况下完成：创建账户、看见额度、创建第一个 Sandbox、打开 Web UI、创建 API Key。
- 所有数据页都有完整的 `loading / empty / validation error / destructive confirmation / success feedback`。
- `Sandbox`、`ApiKey`、`Usage`、`Admin Metering`、`Audit` 页面都能直接映射到真实接口字段与数据库对象，不需要设计师或实现者二次猜字段。
- 第二批 Internal Ops 页面与主产品视觉系统一致，但信息密度更高、容错更强、确认动作更明确。
- 所有探索稿最终都收敛到同一个 `dark flat technical` 系统，不出现一半像 Neon、一半像营销 SaaS 模板的风格漂移。

## Assumptions

- 实现阶段仍以现有 API 为准：`/v1/config`、`/v1/auth/*`、`/v1/auth/cli/*`、`/v1/sandbox-templates`、`/v1/sandboxes*`、`/v1/usage*`、`/v1/admin/*`、`/v1/audit/events`
- Pricing 页面中的 Free / Pro / Ultra 展示，以当前测试与模型中已有额度和限制为准，不扩展到 Stripe checkout
- 外部工具策略固定为：`Stitch` 做探索，`Figma` 做结构化收口，`Codex` 做实现；`Paper` 暂不作为主流程
- 工具可用性参考官方资料：
  - [Google Stitch announcement](https://developers.googleblog.com/stitch-a-new-way-to-design-uis/)
  - [Figma MCP guide](https://help.figma.com/hc/en-us/articles/32132100833559-Guide-to-the-Figma-MCP-server)
  - [Figma MCP troubleshooting](https://developers.figma.com/docs/figma-mcp-server/tools-not-loading/)
  - [Figma rate limits](https://help.figma.com/hc/en-us/articles/34963238552855-What-if-I-m-rate-limited)
  - [Paper MCP docs](https://paper.design/docs/mcp)
