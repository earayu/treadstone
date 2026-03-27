# Treadstone Figma 精修执行计划

> Figma 文件：https://www.figma.com/design/Q8HcutWM4b4W8tTNXqPYKD/Treadstone
> 基于代码版本：v0.5.1
> 关联设计文档：`2026-03-27-treadstone-web-design-plan.md`
> 执行日期：2026-03-27

## 执行摘要

通过 Figma MCP 的 `use_figma` 工具，在 **12 次 API 调用** 中完成了 **169 项文本/命名修改**：
- 8 个顶层 frame 全部按设计文档命名规范重命名
- 全部 8 个屏幕的文案修正（品牌名、标签、占位符、按钮、页脚等）
- Landing 页面的模板规格表完全重写为真实产品数据
- Dashboard 的 tier/额度/单位全部对齐真实后端模型
- 所有 spy-themed 术语替换为标准产品用语

### 完成状态

| 任务 | 状态 |
|------|------|
| Frame 重命名（8 屏） | ✅ 完成 |
| 品牌统一（TREADSTONE → Treadstone） | ✅ 完成 |
| 版本统一（→ v0.5.1） | ✅ 完成 |
| 文案修正（全部 8 屏，~180 项） | ✅ 完成 |
| 不存在功能删除（DEPLOY AGENT 等） | ✅ 完成 |
| 侧栏导航统一 | ✅ 完成 |
| Design Token Variables 创建（40 变量） | ✅ 完成 |
| Design Token 绑定到元素（202 次绑定） | ✅ 完成 |
| 布局/容器尺寸调整 | ✅ 完成 |
| 共享组件提取（Components 页，18 组件） | ✅ 完成 |
| 新增页面（3 个：Usage, SandboxDetail, CliLogin） | ✅ 完成 |
| 缺失页面评估（6 个不需要，已跳过） | ✅ 完成 |

### 最终 Figma 文件结构

**Page 1（设计稿）— 11 个 Frame：**

| Frame | 类型 | 说明 |
|-------|------|------|
| Auth/SignIn | 独立页面 | 登录 |
| Auth/Register | 独立页面 | 注册 |
| App/Dashboard | 独立页面 | 控制台首页 = 沙箱列表 |
| App/ApiKeys | 独立页面 | API Key 管理 |
| App/ApiKeys/CreateModal | 弹窗叠加 | 创建 API Key |
| App/Settings | 独立页面 | 账户设置 |
| App/CreateSandbox | 独立页面 | 创建沙箱 |
| Public/Landing | 独立页面 | 公共首页 |
| App/Usage | 独立页面（新建） | 额度与用量 |
| App/SandboxDetail | 弹窗叠加（新建） | 沙箱详情 |
| Auth/CliLogin | 独立页面（新建） | CLI 登录审批 |

**Components 页 — 组件库：**

| 组件分类 | 组件 |
|----------|------|
| Button | Primary, Secondary, Ghost, Destructive |
| Badge/Status | Ready, Running, Active, Stopped, Completed, Error, Expired, Creating, Pending |
| Badge/Scope | Data Plane, Control Plane |
| Form | Input/Text, Input/Search |
| Table | HeaderRow |
| State | Empty |
| Feedback | Toast |

**不需要的页面（已跳过）：**

| 页面 | 跳过理由 |
|------|----------|
| Public/Pricing | Landing 页已有模板规格表 |
| Public/Quickstart | 外链到文档站 |
| App/Templates | 已集成在 Create Sandbox 的模板选择器中 |
| App/Sandboxes | Dashboard 已经是沙箱列表页 |
| Internal/AdminMetering | 第二批内部运营，推迟 |
| Internal/AuditEvents | 第二批内部运营，推迟 |

## 文件结构总览

### 当前状态

文件只有 1 个 Page（"Page 1"），包含 8 个顶层 frame。无分页、无共享组件、无 Design Token 变量。

| # | 当前 Frame 名称 | Node ID | 尺寸 |
|---|----------------|---------|------|
| 1 | Treadstone Sign-In - Minimalist Gate | 1:2 | 1280×1024 |
| 2 | Treadstone API Keys - High-Density View | 1:73 | 1280×1024 |
| 3 | Treadstone Sign-Up - Focused Entry | 1:355 | 1280×1194 |
| 4 | Treadstone API Keys - Creation Modal | 1:433 | 1280×1024 |
| 5 | Account Settings - Final Refinement | 1:632 | 1280×1024 |
| 6 | Create Sandbox - Technical Form | 1:745 | 1280×1024 |
| 7 | Treadstone Landing - Operational Console | 1:965 | 1280×2979 |
| 8 | Treadstone Dashboard Refined | 1:1220 | 1280×1024 |

### 目标状态

按设计文档统一重命名 frame：

| 当前名称 | → 目标名称 | Node ID |
|----------|-----------|---------|
| Treadstone Sign-In - Minimalist Gate | Auth/SignIn | 1:2 |
| Treadstone API Keys - High-Density View | App/ApiKeys | 1:73 |
| Treadstone Sign-Up - Focused Entry | Auth/Register | 1:355 |
| Treadstone API Keys - Creation Modal | App/ApiKeys/CreateModal | 1:433 |
| Account Settings - Final Refinement | App/Settings | 1:632 |
| Create Sandbox - Technical Form | App/CreateSandbox | 1:745 |
| Treadstone Landing - Operational Console | Public/Landing | 1:965 |
| Treadstone Dashboard Refined | App/Dashboard | 1:1220 |

### 缺失页面（第二阶段创建）

| 设计文档页面 | 优先级 |
|-------------|--------|
| Public/Pricing | P3 |
| Public/Quickstart | P3 |
| App/Templates | P2 |
| App/Sandboxes | P1 |
| App/SandboxDetail | P1 |
| App/Usage | P2 |
| Internal/AdminMetering | P4 |
| Internal/AuditEvents | P4 |
| Auth/CliLogin | P4 |

---

## 全局品牌与术语修正

以下术语在多个页面反复出现，需全局统一：

| Stitch 生成的文案 | → 正确文案 | 依据 |
|------------------|-----------|------|
| TREADSTONE SYSTEMS | Treadstone | 品牌资源 README |
| COMMAND_SURFACE | Treadstone | 品牌名错误 |
| © 2024 | © 2026 | 当前年份 |
| V1.0.4-STABLE / v1.0.4-stable | v0.5.1 | pyproject.toml |
| DEPLOY AGENT | (删除) | 不存在的功能 |
| REGION: US-EAST-1 | (删除) | 不存在的字段 |
| SESSION_ID: AFK-9902-TRDS | (删除) | 不存在的字段 |
| ALL SYSTEMS OPERATIONAL | (删除或简化) | 非产品内功能 |
| Audit Logs (普通用户侧栏) | (删除) | 审计是 Internal Ops |
| Support (侧栏) | (删除) | 不存在的功能 |
| admin_root / PRO PLAN | user@example.com / Free | 默认用户示例 |

### 侧栏导航统一

控制台侧栏应包含（按顺序）：

1. Dashboard
2. Sandboxes
3. Templates
4. API Keys
5. Usage
6. Settings

底部不显示 "Support" 或 "Audit Logs"。

### Footer 统一

- 公共页面 Footer：`© 2026 Treadstone` + `Privacy · Terms · Security · Status`
- 控制台页面 Footer：可省略或极简 status bar

### API Key 前缀格式

真实前缀格式：`sk-`（非 `ts_live_` / `ts_test_`）

---

## 逐屏修改清单

### Screen 1: Auth/SignIn (1:2)

**截图确认：已获取**

| 元素 | 当前值 | → 修改为 | 说明 |
|------|--------|---------|------|
| Frame name | Treadstone Sign-In - Minimalist Gate | Auth/SignIn | 命名规范 |
| 标题 | Sign in to Console | Sign in | 简化 |
| 副标题 | This account manages sandboxes, API keys, usage credits, and browser hand-off links. | Access your sandboxes, API keys, and usage dashboard. | 更自然 |
| Email label | IDENTITY / EMAIL | Email | 用标准表单 label |
| Email placeholder | dev@treadstone.sys | you@example.com | 标准占位符 |
| Password label | ACCESS KEY | Password | 标准 |
| Password link | RECOVER | Forgot password? | 标准 |
| Submit button | SIGN IN | Sign in | Sentence case |
| Divider text | THIRD-PARTY HAND-OFF | Or continue with | 标准 OAuth 分隔 |
| Social: Google | Google | Google | ✓ OK |
| Social: GitHub | GitHub | GitHub | ✓ OK |
| 法律文案 | BY PROCEEDING, YOU ACKNOWLEDGE THE TERMS OF INFRASTRUCTURE USE AND OUR STRICTLY-LOGICAL DATA RETENTION POLICY. | By signing in, you agree to our Terms of Service and Privacy Policy. | 去 spy 化 |
| Footer 版权 | © 2024 TREADSTONE SYSTEMS. ALL RIGHTS RESERVED. | © 2026 Treadstone | 品牌+年份 |
| Footer 链接 | PRIVACY POLICY · TERMS OF SERVICE · SECURITY · SYSTEM STATUS | Privacy · Terms · Security · Status | Sentence case |
| Top nav icons | Help + Settings 图标 | (删除) | 登录页不需要 |
| 背景终端文字 | INIT: TREADSTONE_CORE... 端口扫描文字 | (删除或极大淡化) | 过于 spy-themed |

### Screen 2: App/ApiKeys (1:73)

**截图确认：已获取**

| 元素 | 当前值 | → 修改为 | 说明 |
|------|--------|---------|------|
| Frame name | Treadstone API Keys - High-Density View | App/ApiKeys | 命名规范 |
| Sidebar version | V1.0.4-STABLE | (删除或 v0.5.1) | 版本错误 |
| Sidebar 底部 | admin_root / PRO PLAN | user@example.com / Free | 默认示例 |
| Sidebar nav | Sandboxes, **API Keys**, Usage, Audit Logs, Settings, Support | Dashboard, Sandboxes, Templates, **API Keys**, Usage, Settings | 修正导航 |
| Breadcrumb | KEYS / PRODUCTION | API Keys | 简化 |
| Top nav | DOCS · SYSTEM STATUS · 🔔 · ❓ · DEPLOY AGENT | (删除 DEPLOY AGENT、DOCS、SYSTEM STATUS；保留通知铃铛) | 去掉不存在的功能 |
| 页面标题 | API Keys | API Keys | ✓ OK |
| 页面副标题 | Manage programmatic access for your local and remote services. | Manage programmatic access to the Treadstone API. | 更准确 |
| Search | FILTER KEYS... | Search keys... | 更自然 |
| 创建按钮 | + CREATE API KEY | + Create API Key | Sentence case |
| Stats bar | Active Keys: 12 / Requests (24h): 1.2M / Avg Latency: 14ms / Failed Auth: 0.02% | (整行删除或仅保留 Active Keys 数量) | Requests/Latency/FailedAuth 不存在于产品中 |
| 表格 header | NAME · PREFIX · SCOPE · CREATED AT · LAST USED · EXPIRY · ACTIONS | Name · Key Prefix · Scope · Created · Updated · Expires · Actions | 字段名对齐 API |
| 示例 key prefix | ts_live_9a2f... / ts_live_k1l8... / ts_live_p9x3... / ts_test_x7v2... / ts_live_m4q9... | sk-9a2f... / sk-k1l8... / sk-p9x3... / sk-x7v2... / sk-m4q9... | 真实前缀格式 |
| Scope badges | DATA PLANE / CONTROL PLANE | Data Plane / Control Plane | Sentence case |
| Expiry 红字 | Expired | Expired | ✓ OK |
| Footer 左 | SHOWING 1-12 OF 12 KEYS • REGION: US-EAST-1 | Showing 1–5 of 5 keys | 去掉 Region |
| Footer 右 | SYSTEM OPERATIONAL SESSION_ID: AFK-9902-TRDS | (删除) | 不存在 |
| Footer 版权 | © 2024 TREADSTONE SYSTEMS INC. | © 2026 Treadstone | 品牌 |

### Screen 3: Auth/Register (1:355)

**截图确认：已获取**

| 元素 | 当前值 | → 修改为 | 说明 |
|------|--------|---------|------|
| Frame name | Treadstone Sign-Up - Focused Entry | Auth/Register | 命名规范 |
| Top nav brand | COMMAND_SURFACE | TREADSTONE | **严重错误**：品牌名完全错误 |
| Top nav links | Docs · Changelog · Pricing | Docs · Pricing · Quickstart | Changelog 不存在 |
| Top nav right | Sign In | Sign In | ✓ OK |
| 标题 | Initiate Environment | Create Account | 去 spy 化 |
| 副标题 | Deploy your first instance on the Treadstone mesh. | Create your Treadstone account to get started. | 更自然 |
| Social buttons | GitHub · Google | GitHub · Google | ✓ OK |
| Divider | OR EMAIL | Or sign up with email | 更清晰 |
| Email label | IDENTITY ENDPOINT | Email | 标准 |
| Email placeholder | dev@treadstone.io | you@example.com | 标准 |
| Password label | ACCESS CIPHER | Password | 标准 |
| Submit button | Create Account → | Create Account | 去箭头 |
| 免费额度提示 | New users start on the free tier: **10 vCPU-hours monthly** + **50 vCPU-hours** welcome bonus. All core modules included. | New users start on the free tier: **10 vCPU-hours monthly** + **50 vCPU-hours** welcome bonus. All sandbox templates included. | "core modules" → "sandbox templates" |
| 法律文案 | By clicking "Create Account", you agree to the **Service Protocols** and **Privacy Logic**. | By creating an account, you agree to the **Terms of Service** and **Privacy Policy**. | 标准法律术语 |
| Footer 版权 | © 2024 COMMAND_SURFACE | © 2026 Treadstone | 品牌+年份 |
| Footer links | Privacy · Terms · Security · Status | Privacy · Terms · Security · Status | ✓ OK |

### Screen 4: App/ApiKeys/CreateModal (1:433)

**截图确认：已获取**

| 元素 | 当前值 | → 修改为 | 说明 |
|------|--------|---------|------|
| Frame name | Treadstone API Keys - Creation Modal | App/ApiKeys/CreateModal | 命名规范 |
| Modal title | CREATE NEW API KEY | Create API Key | Sentence case，简化 |
| Modal subtitle | Define scope and access for the new credential. | Configure access scope for the new API key. | 更准确 |
| Label: Name | KEY NAME | Name | 简化 |
| Placeholder: Name | e.g. user-service-worker | e.g. my-api-key | 更通用 |
| Label: Expiry | OPTIONAL EXPIRATION | Expiration (optional) | Sentence case |
| Toggle label | CONTROL PLANE ACCESS | Control Plane Access | Sentence case |
| Toggle desc | Allows managing sandboxes and keys | Allows managing sandboxes and API keys | 补全 |
| Scope title | DATA PLANE SCOPE | Data Plane Scope | Sentence case |
| Scope tabs | NONE · ALL · SELECTED | None · All · Selected | Sentence case |
| Sandbox list title | SELECT SANDBOX IDS | Select Sandboxes | 简化 |
| Cancel button | CANCEL | Cancel | Sentence case |
| Submit button | GENERATE API KEY | Create API Key | 与创建按钮一致 |
| 背景 sidebar version | v1.0.4-stable | (忽略，模态框遮挡) | |

### Screen 5: App/Settings (1:632)

**截图确认：已获取**

| 元素 | 当前值 | → 修改为 | 说明 |
|------|--------|---------|------|
| Frame name | Account Settings - Final Refinement | App/Settings | 命名规范 |
| Breadcrumb | SETTINGS / ACCOUNT | Settings | 简化 |
| 页面标题 | Account Metadata | Account Settings | 去 spy 化 |
| 页面副标题 | Manage your architectural identity and security parameters within the Treadstone Control Plane. | Manage your account settings. | 极简 |
| Section 1 title | IDENTITY | Profile | 更通用 |
| Section 1 desc | Core authentication metadata | (删除) | 多余 |
| "EDIT PROFILE" 按钮 | EDIT PROFILE | (删除) | 无此功能 |
| Field: Email | EMAIL ADDRESS · admin@treadstone.ai | Email · user@example.com | 标准 |
| Field: Role | USER ROLE · System Architect ■ | Role · ro | 真实角色枚举 |
| Field: UID | UNIQUE IDENTIFIER (UID) · USR-9921-TS-882 | User ID · a1b2c3d4-... | 真实 UUID 格式 |
| Field: Date | REGISTRATION DATE · 2023-11-04 14:22:01 UTC | Created · 2026-01-15 | 简化 |
| Section 2 title | ACCESS | Security | 更通用 |
| Section 2 desc | Security & Credential Management | (删除) | 多余 |
| Password row | Password Management · Last rotated 42 days ago | Change Password | 简化 |
| Password button | CHANGE PASSWORD | Change Password | Sentence case |
| 新增 | (无) | Sign Out 按钮 | 设计文档要求 |
| Footer 左 | REGION: US-EAST-1 LATENCY: 14MS | (删除) | 不存在 |
| Footer 右 | ALL SYSTEMS OPERATIONAL | (删除) | 不存在 |
| Sidebar brand | Treadstone / AI CONTROL PLANE | Treadstone | 简化 |

### Screen 6: App/CreateSandbox (1:745)

**截图未获取，基于元数据分析**

| 元素 | 当前值 | → 修改为 | 说明 |
|------|--------|---------|------|
| Frame name | Create Sandbox - Technical Form | App/CreateSandbox | 命名规范 |
| 页面标题 | Create Sandbox | Create Sandbox | ✓ OK |
| Template label | Instance Template | Template | 简化 |
| Template 选项展示 | tiny / small / medium / large / xl | AIO Sandbox Tiny / Small / Medium / Large / XLarge | 匹配 display_name |
| Name label | Sandbox Name (Optional) | Name (optional) | 简化 |
| Name hint | Lowercase, numbers, hyphens only. 1-55 chars. | Lowercase letters, numbers, or hyphens. 1–55 characters. | 稍微调整措辞 |
| Labels label | Environment Labels | Labels | 简化 |
| Labels placeholder | key:value, env:dev | key:value, env:dev | ✓ OK |
| Auto-stop label | Auto-Stop Interval | Auto-Stop Interval | ✓ OK |
| Storage sizes | (需确认) | 5Gi / 10Gi / 20Gi | 匹配 StorageSize Literal |
| Sidebar | (需确认) | 统一为标准导航 | 同上 |
| 面包屑 / back link | (需确认) | ← Back to Sandboxes | 添加返回链接 |

### Screen 7: Public/Landing (1:965)

**截图未获取，基于元数据分析**

| 元素 | 当前值 | → 修改为 | 说明 |
|------|--------|---------|------|
| Frame name | Treadstone Landing - Operational Console | Public/Landing | 命名规范 |
| Section title | SECURE AGENT HAND-OFF PROTOCOL | Browser Hand-off | 去 spy 化 |
| Hero 描述 | (需确认) | 对齐设计文档 prompt 中的产品定位 | |
| CTA 按钮 | (需确认) | Start free / Read docs | 匹配设计文档 |
| 模板/规格预览 | (需确认) | tiny/small/medium/large/xlarge + CPU/Memory | |
| CLI 示例 | (需确认) | `pip install treadstone-cli` | 真实安装命令 |
| Footer | (需确认) | © 2026 Treadstone + 标准链接 | |

### Screen 8: App/Dashboard (1:1220)

**截图未获取，基于元数据分析**

| 元素 | 当前值 | → 修改为 | 说明 |
|------|--------|---------|------|
| Frame name | Treadstone Dashboard Refined | App/Dashboard | 命名规范 |
| Tier 显示 | Current Tier (Pro) | Current Tier · Free | 默认免费层 |
| 额度显示 | (需确认) | 10 vCPU-hours monthly / 50 vCPU-hours bonus | 匹配真实免费额度 |
| 最大并发 | (需确认) | 1 concurrent sandbox | 匹配 max_concurrent_running |
| 最长时长 | (需确认) | 30 min max duration | 匹配 1800s |
| Create 按钮 | Create Sandbox | + Create Sandbox | ✓ 基本 OK |
| Sidebar | (需确认) | Dashboard, Sandboxes, Templates, API Keys, Usage, Settings | 标准导航 |

---

## Design Token 变量（Figma Variables）

在 Figma 中创建 Variable Collection "Treadstone Tokens"，按设计文档定义：

### Color Tokens

| Token 名称 | Dark Mode 值 | 说明 |
|-----------|-------------|------|
| color/bg/canvas | #0A0A0A | 主背景 |
| color/bg/sidebar | #111111 | 侧栏背景 |
| color/bg/surface | #161616 | 卡片/表格行背景 |
| color/bg/surface-muted | #1A1A1A | 弱化表面 |
| color/border/default | #2A2A2A | 默认边框 |
| color/border/subtle | #1F1F1F | 弱化边框 |
| color/text/primary | #EDEDED | 主文字 |
| color/text/secondary | #A1A1A1 | 次要文字 |
| color/text/muted | #666666 | 弱化文字 |
| color/link/default | #00E599 | 链接色（Treadstone 绿） |
| color/success/default | #00E599 | 成功状态 |
| color/warning/default | #F5A623 | 警告状态 |
| color/danger/default | #FF4444 | 危险/错误 |
| color/accent/primary | #00E599 | 主强调色（CTA 按钮） |

### Spacing Tokens

| Token | 值 |
|-------|-----|
| space/2 | 2px |
| space/4 | 4px |
| space/8 | 8px |
| space/12 | 12px |
| space/16 | 16px |
| space/20 | 20px |
| space/24 | 24px |
| space/32 | 32px |

### Radius Tokens

| Token | 值 |
|-------|-----|
| radius/sm | 4px |
| radius/md | 6px |
| radius/lg | 8px |

### Shadow Tokens

| Token | 值 |
|-------|-----|
| shadow/none | none |
| shadow/subtle | 0 1px 2px rgba(0,0,0,0.3) |

---

## 执行优先级

### Phase 1: 批量文本修正（单次 use_figma 调用）

1. 重命名所有 8 个顶层 frame
2. 修正 Sign-In 页面所有文案
3. 修正 Sign-Up 页面所有文案（特别是 COMMAND_SURFACE → Treadstone）
4. 修正 API Keys 页面文案
5. 修正 Account Settings 页面文案
6. 修正 API Key 创建弹窗文案

### Phase 2: Design Token 建立（1-2 次 use_figma 调用）

1. 创建 Variable Collection
2. 定义所有颜色、间距、圆角 Token

### Phase 3: 侧栏统一（1 次 use_figma 调用）

1. 统一所有控制台页面的侧栏导航项
2. 修正侧栏品牌文字和版本

### Phase 4: 布局调整

1. 删除不存在的功能元素（DEPLOY AGENT、Stats bar 虚假指标等）
2. 调整 Landing 页面的 spy-themed 文案
3. 调整 Dashboard 的额度显示

### Phase 5: 缺失页面创建（后续迭代）

按 P1-P4 优先级创建缺失的 9 个页面。

---

## Figma MCP 调用预算

Starter 计划每小时约 10 次调用。精修工作预估需要：

- Phase 1: 3-5 次 `use_figma` 调用（批量文本修正）
- Phase 2: 1-2 次 `use_figma` 调用（Token）
- Phase 3: 1-2 次 `use_figma` 调用（侧栏）
- Phase 4: 2-3 次 `use_figma` 调用（布局）
- 截图验证: 若干 `get_screenshot` 调用

建议在多个小时段内分批执行，或升级 Figma 计划以获得更高配额。
