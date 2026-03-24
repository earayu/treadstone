# Sandbox Web UI 登录与 Hand-off 设计归档

**日期：** 2026-03-24  
**状态：** 已实现  
**关联 Issue：** [#60 Harden sandbox subdomain Web UI with browser-scoped sessions](https://github.com/earayu/treadstone/issues/60)

## 背景

Treadstone 的 Web UI 几乎完全是给人类使用的，但入口经常由 AI Agent 代为创建和分发。因此浏览器链路需要同时满足两件事：

1. 已登录用户直接打开 Sandbox Web URL 时，体验要尽量像“天然可访问”。
2. Agent 可以把一个可以直接打开的链接交给未登录的人类，实现顺滑的 hand-off。

同时，这条链路不应该把控制面 API Key 暴露给浏览器，也不应该把控制面的全局登录 cookie 直接共享到所有 Sandbox 子域名。

## 最终决策

### 1. 继续使用 Sandbox 子域名作为 Web UI 的最终承载地址

保留生产 URL 形态：

```text
https://sandbox-{name}.treadstone-ai.dev/
```

这是最终真正承载 Web UI 的 origin。VNC、VS Code、Jupyter、Browser panel、同源 cookie 与 WebSocket 都继续落在这个子域名上。

### 2. 控制面 cookie 不共享到所有 Sandbox 子域名

控制面 `session` cookie 仍然只留在 API 域名。  
当浏览器第一次进入某个 Sandbox 子域名时，系统会自动把控制面登录态换成该 Sandbox 专属的浏览器 cookie `ts_bui`。

这个取舍的原因不是“共享一定不安全”，而是：

- 共享控制面 cookie 对用户体验提升不大
- 但会把账号级登录态扩张到所有 Sandbox origin
- 后续如果 Web UI 继续扩展，边界会越来越难收回来

### 3. 引入当前唯一的 `open_link`

每个 Sandbox 维护一条当前有效的 `open_link`：

- 由控制面生成或重置
- 可被未登录浏览器直接消费
- 适合 agent-to-human hand-off
- 删除或重建后，旧链接立即失效

这是一个有意识的产品取舍：相较于一次性 ticket，更贴近“Agent 创建后把页面交给人看”的真实使用方式。

### 4. `urls.web` 改为返回推荐打开入口，而不是裸 canonical URL

这是这次实现里最重要的接口语义变化。

现在的 `SandboxResponse.urls.web` 表示：

- **推荐给人类或 Agent 打开的浏览器入口 URL**
- 如果当前 Sandbox 已启用 `open_link`，返回 hand-off URL
- 如果当前没有启用 `open_link`，则回退为 canonical 子域名 URL

因此：

- `urls.web` 现在更像“可直接打开”的产品入口
- 而不是“这个 Sandbox 最终承载页面的 origin”

canonical origin 仍然存在，但它作为内部概念保留在网关和 `GET /v1/sandboxes/{id}/web-link` 的 `web_url` 字段中。

### 5. `GET /web-link` 不返回明文 link，但控制面对象会返回可用入口

控制面仍保留：

- `POST /v1/sandboxes/{sandbox_id}/web-link`
- `GET /v1/sandboxes/{sandbox_id}/web-link`
- `DELETE /v1/sandboxes/{sandbox_id}/web-link`

语义为：

- `POST`：创建或重建当前唯一 hand-off link，并返回完整 `open_link`
- `GET`：查看当前 link 是否存在、何时过期、最后使用时间，但不返回明文 link
- `DELETE`：撤销当前 hand-off link

而 `GET /v1/sandboxes/{id}`、`GET /v1/sandboxes` 等 Sandbox 资源接口会直接把当前 hand-off 入口暴露到 `urls.web` 中，便于 Agent 无额外接口调用就能拿到最终可打开链接。

## 认证与会话模型

### 1. 三种浏览器相关凭证

- **控制面 cookie**
  - 仅限 API 域名
  - 用于 bootstrap 和控制面操作

- **bootstrap ticket**
  - 短期 JWT
  - 仅用于“已登录用户访问 canonical URL 时”的一次跳转交换
  - 默认 TTL：5 分钟

- **sandbox web cookie (`ts_bui`)**
  - 只绑定单个 Sandbox 子域名
  - 不落库
  - 默认 TTL：30 天
  - 表示该浏览器可以继续访问这个 Sandbox 的 Web UI

### 2. `open_link`

当前实现中，`open_link` 的可见 token 不再是“只存 hash 的一次性 secret”，而是：

- 与当前 `SandboxWebLink` 行主键同值的 opaque token
- 默认 TTL：7 天
- 当前一个 Sandbox 只有一个有效 token

之所以采用这个更简单的模型，是因为：

- `urls.web` 需要能够稳定返回当前 hand-off URL
- `GET /sandboxes` / `GET /sandboxes/{id}` 不适合在读取时偷偷轮换 token
- 如果仍坚持“数据库只存 hash，不存可重建 token”，控制面读接口就无法返回当前完整 hand-off URL

这是一个刻意的产品与工程折中：

- 安全边界仍然只落在单 Sandbox Web UI
- token 默认短于浏览器 cookie
- 但换来简单、直接、可复用的 hand-off 体验

## 主要浏览器流程

### 1. 已登录用户直接访问 canonical Web UI URL

流程：

1. 浏览器访问 `https://sandbox-{name}.…/`
2. 若已有 `ts_bui`，直接进入
3. 若没有，子域名跳转到 `GET /v1/browser/bootstrap`
4. API 域名检查控制面登录态
5. 若已登录，生成 bootstrap ticket
6. 浏览器跳回 `/_treadstone/open?ticket=...`
7. 子域名设置 `ts_bui`
8. 再跳回干净 URL

用户最终感知接近“直接打开就成功”。

### 2. 未登录用户通过 hand-off link 打开

流程：

1. Agent 通过控制面创建或重建当前 `open_link`
2. 人类浏览器打开 `open_link`
3. 子域名 `/_treadstone/open?token=...` 校验 token
4. 校验成功后设置 `ts_bui`
5. 再跳到干净的 canonical URL

最终浏览器停留在正常 Web UI 地址，而不是长时间把 token 暴露在地址栏。

### 3. 未登录用户直接访问 canonical URL

流程：

1. 浏览器进入 Sandbox canonical URL
2. 没有 `ts_bui`
3. 重定向到 `GET /v1/browser/bootstrap`
4. 若没有控制面 cookie，再进入 `GET /v1/browser/login`
5. 浏览器登录成功后回到 bootstrap
6. bootstrap 继续换票并设置 `ts_bui`

## 数据模型

新增表：`sandbox_web_link`

字段语义：

- `id`
  - 当前 `open_link` token 本体
  - 也是控制面内该 link 的稳定标识
- `sandbox_id`
  - 每个 Sandbox 唯一
- `created_by_user_id`
  - 最近一次生成或重建该 link 的用户
- `gmt_created`
- `gmt_updated`
- `gmt_expires`
- `gmt_last_used`
- `gmt_deleted`

约束：

- `sandbox_id` 全局唯一
- 删除后不新建第二行，而是在原行上重置 token 与生命周期

这样能避免：

- 删除后重新创建撞唯一约束
- 控制面无法重建当前链接
- 同一 Sandbox 存在多个相互竞争的 hand-off 链接

## 网关边界与透传策略

### 1. 只剥离 Treadstone 自己的浏览器鉴权 cookie

这次实现后，子域名网关只移除：

- `ts_bui`

不再移除：

- sandbox 应用自己的 `session` cookie
- sandbox 应用的 `Authorization` 头

原因：

- API 控制面的 `session` cookie 本来就是 host-scoped 到 API 域名，不会自然出现在 Sandbox 子域名请求里
- 无脑删除 `session` 会误伤 Flask / Starlette / Django 等默认会话机制
- 无脑删除 `Authorization` 会破坏 Sandbox 应用自己的 Bearer / Basic Auth

### 2. 保留 cookie 的原始编码形式

在重建转发用 `Cookie` 头时，使用 `coded_value` 而不是普通解码值，避免破坏：

- 带空格的 quoted cookie
- JSON cookie
- 其他依赖 quoting / escaping 的 cookie 值

### 3. 公开子域名部署时强校验 `TREADSTONE_API_BASE_URL`

如果：

- 配置了公开 `sandbox_domain`
- 但 `TREADSTONE_API_BASE_URL` 仍是 `localhost`

则启动时 fail-fast。

原因是当前子域名访问缺少 `ts_bui` 时一定会重定向到：

```text
{TREADSTONE_API_BASE_URL}/v1/browser/bootstrap
```

若公开域名环境里仍跳到 `localhost`，浏览器链路必然不可用，提早失败比静默错误更可接受。

本地开发依然允许：

- `sandbox.localhost`
- `http://localhost:8000`

## 对 review 意见的处理

这次实现后，相关 review 结论如下：

### 1. Preserve sandbox app Authorization headers

**采纳。**

Sandbox 应用本身完全可能在同源请求中使用 `Authorization`。  
子域名网关的职责是剥离 Treadstone 自己的浏览器凭证，而不是替 Sandbox 应用决定认证方式。

### 2. Stop deleting the sandbox app's own `session` cookie

**采纳。**

控制面 cookie 与 Sandbox 子域名并不共享 host。  
删除所有名为 `session` 的 cookie 会破坏 Sandbox 应用自己的登录态。

### 3. Re-encode surviving cookies before forwarding

**采纳。**

重建 `Cookie` 头时必须保留原始 quoting / escaping，否则会让上游应用收到语义不同的 cookie。

### 4. Validate `api_base_url` before redirecting sandbox browsers

**采纳。**

公开 Sandbox 子域名一旦跳向 `localhost`，整条 Web UI 链路就不可用了，属于启动期就应发现的错误配置。

### 5. Clear `last_used_at` when rotating a web link

**采纳。**

重新生成的新 link 不应该继承旧 link 的“已使用”状态。

## 已落地的接口语义

### 控制面

- `POST /v1/sandboxes/{sandbox_id}/web-link`
  - 创建或重建当前唯一 hand-off link
- `GET /v1/sandboxes/{sandbox_id}/web-link`
  - 返回 `web_url`、`enabled`、`expires_at`、`last_used_at`
- `DELETE /v1/sandboxes/{sandbox_id}/web-link`
  - 撤销当前 hand-off link

### 浏览器辅助入口

- `GET /v1/browser/bootstrap`
- `GET /v1/browser/login`
- `POST /v1/browser/login`

### Sandbox 资源接口

- `SandboxResponse.urls.web`
  - 现在表示推荐浏览器入口 URL
  - 优先返回当前 hand-off link

## 不做的事情

这次有意识地没有实现以下能力：

- 多条命名 `open_link`
- 浏览器会话强制下线
- 删除 hand-off link 时立即踢掉已拿到 `ts_bui` 的浏览器
- 把控制面 API Key 直接暴露到浏览器
- 把控制面 cookie 共享到所有 Sandbox 子域名

这些都可以以后再加，但当前版本刻意优先“清晰、顺手、够用”。

## 本地验证

本次落地后已完成以下验证：

- `uv run pytest -q`
- `make lint`
- `make gen-sdk`
- `make migrate`

同时新增了专门的回归测试覆盖：

- `urls.web` 返回当前 hand-off URL
- `open_link` 轮换与删除行为
- `last_used_at` 在轮换后清空
- Sandbox 应用自己的 `Authorization` / `session` / quoted cookies 不被误删
- 公开 `sandbox_domain` + 本地 `api_base_url` 配置会 fail-fast
