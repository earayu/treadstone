# Treadstone 中文文档

本目录不再区分 `design/` 和 `plans/`。从现在开始，中文文档统一按当前代码里已经存在的功能模块组织，目标是让文档可以直接反映今天的控制面能力，而不是保留按阶段推进时留下的历史叙事。

## 文档原则

- **代码优先**：接口、字段、状态机、约束、默认值都以 `treadstone/`、`alembic/` 和测试为准。
- **高层表达**：即使某个主题过去是实施计划，现版本也统一写成功能设计视角，不再按“Task 1/Task 2”拆解。
- **只写当前实现**：已移除或尚未落地的想法不会继续当作现状描述。
- **把差异写清楚**：如果当前实现里仍有命名不统一、接线未完全闭环的地方，会明确标注为“当前代码现状”。

## 当前 6 个功能模块

1. [认证与访问控制](./modules/01-auth-and-access.md)
2. [Sandbox 模板与生命周期](./modules/02-sandbox-lifecycle-and-templates.md)
3. [浏览器接管与数据面代理](./modules/03-browser-handoff-and-data-plane.md)
4. [Agent 接入面：API、CLI 与 Python SDK](./modules/04-agent-clients-and-api-surface.md)
5. [计量、套餐与管理员运营](./modules/05-metering-and-admin-ops.md)
6. [控制面运行时、审计与部署](./modules/06-control-plane-runtime-and-deployment.md)

## 这次重组覆盖了什么

旧文档里的这些主题，已经被折叠进上面的 6 个模块：

- Phase 0/1/2/5 的脚手架、认证、Sandbox API、Leader Election
- 双路径供给、多规格模板、子域名网关、Web hand-off、CLI 浏览器登录
- SDK/CLI 设计与实施计划
- 计量总览、Compute、Storage、Enforcement、Execution Plan
- 部署、测试、CI、Make 工作流

## 不再作为“当前功能文档”的主题

以下内容在历史文档里出现过，但它们不代表当前仓库已经实现的功能，因此不再单独保留为现状文档：

- Marketplace / Skill Pack 市场
- Stripe Checkout、发票、充值等支付闭环
- 独立的前端控制台实现
- Figma/Stitch 页面设计执行稿
- 邀请注册流程
- 外部 OIDC Bearer 主认证模式（`auth0` / `authing` / `logto`）

## 维护方式

后续如果代码继续演进，推荐按下面的顺序维护文档：

1. 先判断改动属于哪个模块。
2. 直接更新对应模块文档，而不是再新增日期型设计稿。
3. 如果改动跨模块，再更新本总览中的模块边界说明。

