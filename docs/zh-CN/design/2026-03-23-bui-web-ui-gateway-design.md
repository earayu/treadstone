# BUI Web UI Gateway 设计

**日期：** 2026-03-23

**状态：** Draft

**目标：** 为 Treadstone 的浏览器 Web UI 提供一个独立于 API 域名的 `bui` 入口方案，在不强依赖付费通配符证书的前提下，稳定支持 VNC、VS Code Terminal、Jupyter、浏览器截图/控制等浏览器内能力。

**假设：** 本文将 `bui` 解释为 Browser UI 专用入口域名，不再与 `api.treadstone-ai.dev` 复用同一个 Host。首选形态为单域名 `bui.treadstone-ai.dev`，可选形态为 `*.bui.treadstone-ai.dev`。

---

## 1. 问题说明

### 1.1 当前线上问题

当前 CLI / API 返回的 Web UI 地址形如：

```text
http://{sandbox-name}.api.treadstone-ai.dev/
```

这条链路在生产上不可用，主要不是浏览器本地网络问题，而是接入设计尚未闭环：

1. **DNS 未对每个 Sandbox 子域名做泛解析**
   - `api.treadstone-ai.dev` 本身可解析，但 `{sandbox-name}.api.treadstone-ai.dev` 当前不解析。

2. **生产 Ingress 只声明了 `api.treadstone-ai.dev`**
   - 现有 prod Ingress 只配置了单一 host，没有为 Sandbox Web UI 准备独立 host 规则。

3. **生产证书只覆盖 API Host**
   - 当前证书配置面向 `api.treadstone-ai.dev`，不覆盖任意 Sandbox 子域名。

4. **当前子域名 Web UI 入口没有鉴权**
   - `SandboxSubdomainMiddleware` 仅按 Host 提取 sandbox id 并直接反向代理到 Pod，没有经过 `get_current_user()`、ownership 校验或 sandbox token 校验。

5. **当前 `urls.web` 的 scheme 仍依赖 API 请求上下文**
   - `urls.web` 当前基于 `request.base_url` 生成；若 Ingress / ALB / proxy headers 未正确透传，接口可能返回 `http://...` 而不是期望的 `https://...`。

6. **当前 path proxy 适合 Agent/SDK，不适合直接承载完整浏览器 UI**
   - 现有 `/v1/sandboxes/{id}/proxy/{path}` 是“薄透传”实现，没有处理前缀感知、`Location` 重写、`Set-Cookie Path` 重写等浏览器场景常见问题。

### 1.2 为什么之前的 path 方案会出问题

之前尝试把完整 Web UI 挂到 path 前缀下，例如：

```text
/v1/sandboxes/{id}/proxy/index.html
```

这条路**不是原理上不可行**，但对代理层要求比 Agent/SDK 调用高很多。即使 WebSocket 已经打通，仍然可能因为以下原因导致页面或资源不正常：

- HTML / JS / CSS / 图片等资源使用绝对路径 `/...`
- `Location: /foo` 或 `Location: https://host/foo` 跳出当前前缀
- `Set-Cookie: Path=/` 导致不同 Sandbox 的 cookie 相互污染
- 上游服务需要 `X-Forwarded-Prefix` / `X-Forwarded-Host` / `X-Forwarded-Proto`
- 某些子服务对 base path 敏感，但当前代理没有做任何补偿

结论：**path 方案可行，但必须引入“前缀感知的 Browser Gateway”，不能继续使用当前薄透传代理直接承载整套 Web UI。**

---

## 2. 当前代码库现状

### 2.1 Web URL 的生成方式

`urls.web` 由 `treadstone/api/sandboxes.py` 基于 `settings.sandbox_domain` 拼接生成：

```python
web = f"{scheme}://{sb.name}.{settings.sandbox_domain}{_web_port_suffix(base)}"
```

这意味着当前实现默认假设“每个 Sandbox 都有自己的子域名”，且该域名与 API 服务共享同一套入口层能力。

同时，`scheme` 来源于请求上下文，而不是显式的 Web UI 配置；这会使 `urls.web` 与 Ingress / ALB 的 `X-Forwarded-Proto` 行为产生耦合。

### 2.2 子域名代理的能力边界

`treadstone/middleware/sandbox_subdomain.py`：

- 支持 HTTP
- 支持 WebSocket
- 仅靠 Host 提取 sandbox id
- **不做认证与授权**
- 不依赖 DB 状态

这使它非常适合作为本地开发或受控内网实验入口，但不适合直接作为公网生产浏览器入口。

### 2.3 Path Proxy 的能力边界

`treadstone/api/sandbox_proxy.py` + `treadstone/services/sandbox_proxy.py`：

- 经过 `get_current_user()` 认证
- 校验 sandbox owner
- 依赖 DB 状态为 `READY`
- 支持 HTTP
- 当前仓库里的公开路由只看到 HTTP path proxy，缺少浏览器前缀重写逻辑
- 仅过滤 hop-by-hop headers，不重写 `Location` / `Set-Cookie`

它更像“受控数据面 API 入口”，而不是“浏览器可直接使用的完整 UI Gateway”。

### 2.4 生产部署现状

当前 prod Helm values 中：

- 只有 `api.treadstone-ai.dev`
- 只有一个证书 id
- 没有 `bui.treadstone-ai.dev` 或 `*.bui.treadstone-ai.dev`
- API 侧浏览器 session cookie 仍默认 `secure=false`

因此现在的生产部署拓扑并未为 Browser UI 预留独立入口。

---

## 3. 外部调研结论

### 3.1 agent-infra/sandbox 本身并不排斥 path 方案

上游 AIO Sandbox 文档中的 Preview Proxy 明确支持代理端口，并区分：

- `/proxy/{port}/`：更适合后端服务
- `/absproxy/{port}/`：更适合前端页面

同时文档仍明确标注 **SubDomain Proxy(Recommend)**，说明：

- 子域名方案对浏览器最自然
- path 方案可行，但通常需要更多前缀处理

### 3.2 上游近期已经补了 subpath 兼容性

`agent-infra/sandbox` 在 2025-11 的两个 release 中连续修复了子路径问题：

- `v1.0.0.151`：修复 AIO 首页通过 subpath 暴露时的 404
- `v1.0.0.152`：`/v1/browser/info` 支持 `X-Forwarded-Prefix`

这说明：

- “子路径方案不行”并不是结论
- 只要代理正确传前缀，并且镜像版本足够新，路径方案具备可行性

### 3.3 code-server 等浏览器 IDE 一直对 base path 敏感

code-server 官方文档长期建议：

- 优先使用子域名代理
- 若使用子路径代理，需要保证 base path、proxy headers、WebSocket、重定向、静态资源都正确处理

这和我们遇到的问题高度一致。

---

## 4. 设计目标

### 4.1 目标

- 为浏览器 Web UI 提供独立于 API 的访问入口
- 让 `bui` 入口不依赖付费通配符证书即可上线
- 让 HTTP、WebSocket、下载、重定向、cookie 在同一方案下统一工作
- 让浏览器入口具备认证、授权和 sandbox 级别隔离能力
- 保留未来升级到 `*.bui` 子域名模式的空间

### 4.2 非目标

- 本次不解决 K8s → DB 状态同步滞后问题
- 本次不改造上游 AIO Sandbox 镜像本身
- 本次不要求替换现有 Agent/SDK 使用的 path proxy

---

## 5. 方案选型

### 5.1 方案 A：`*.bui.treadstone-ai.dev`

示例：

```text
https://{sandbox-name}.bui.treadstone-ai.dev/
```

优点：

- 浏览器最自然
- 相对路径 / WS / 下载最少改造
- 最接近当前 `sandbox_domain` 设计

缺点：

- 需要 wildcard DNS
- 需要 wildcard TLS
- 若继续用当前 middleware，还需要补认证与授权

适合：

- 已接受 wildcard DNS + TLS 成本
- 追求最少 UI 兼容处理

### 5.2 方案 B：单域名 `bui.treadstone-ai.dev` + 路径前缀

示例：

```text
https://bui.treadstone-ai.dev/s/{sandbox-name}/
```

优点：

- 只需要**单域名证书**
- 与 `api.treadstone-ai.dev` 完全解耦
- 更容易集中处理认证、审计、限流、下载和 cookie 隔离
- 更容易在同一入口实现“打开 Web UI”跳转逻辑

缺点：

- 需要前缀感知代理
- 需要响应重写
- 对浏览器 UI 兼容性要求更高

适合：

- 不想购买付费通配符证书
- 接受在 Treadstone 网关层做一次正确的前缀治理

### 5.3 结论

**推荐采用方案 B 作为默认生产方案。**

原因：

1. 解决了“单域名证书”与“浏览器独立入口”的矛盾
2. 不再依赖 `*.api.treadstone-ai.dev`
3. 便于在 Treadstone 内部统一补齐认证与前缀问题
4. 若未来愿意引入 wildcard DNS/TLS，可平滑升级为方案 A

---

## 6. 推荐设计：BUI Gateway（单域名 + 路径前缀）

## 6.1 URL 形态

API 继续保持：

```text
https://api.treadstone-ai.dev
```

Browser UI 改为：

```text
https://bui.treadstone-ai.dev/s/{sandbox-name}/
```

可选地使用 sandbox id 替代 name：

```text
https://bui.treadstone-ai.dev/s/{sandbox-id}/
```

推荐优先使用 **sandbox name** 作为展示 URL，内部再映射到 DB id / k8s name。

## 6.2 组件划分

新增一个“BUI Gateway”逻辑层，职责如下：

1. 校验浏览器访问凭证
2. 根据 path 中的 sandbox name / id 解析目标 Sandbox
3. 校验 owner / token scope
4. 将请求代理到对应 sandbox Pod
5. 为上游补齐 `X-Forwarded-*`
6. 重写 `Location` 与 `Set-Cookie`
7. 支持 HTTP + WebSocket

可实现为：

- 新的 FastAPI router + websocket route
- 或新的 ASGI middleware（仅拦截 `Host == bui.treadstone-ai.dev`）

**推荐：router + websocket route，而不是裸 middleware。**

原因：

- 更容易复用现有依赖注入与鉴权逻辑
- 更容易查询 DB / 校验 ownership
- 更容易编写测试
- 更容易对失败场景返回统一错误 envelope

## 6.3 建议新增配置

```python
sandbox_web_mode: str = "path"          # path | subdomain
sandbox_web_host: str = ""              # e.g. bui.treadstone-ai.dev
sandbox_web_domain: str = ""            # e.g. bui.treadstone-ai.dev (subdomain mode only)
sandbox_web_path_prefix: str = "/s"
sandbox_web_token_ttl: int = 300        # 5 minutes
cookie_secure: bool = True
```

说明：

- `sandbox_domain` 保留给旧子域名逻辑 / local dev
- 新增 `sandbox_web_*` 专门描述浏览器入口
- `urls.web` 应优先根据 `sandbox_web_mode` 生成

## 6.4 建议的认证模型

不建议直接把主 API session cookie 跨 host 透传到 `bui`。

推荐新建 **BUI Session / BUI Token**：

### 入口流程

1. 用户在已登录 API 的上下文里点击“Open Web UI”
2. 控制面生成一个短时效 BUI token
3. 控制面 302 到：

```text
https://bui.treadstone-ai.dev/open/{sandbox-name}?token=...
```

4. BUI Gateway 校验 token 后，设置仅作用于该 Sandbox 前缀的 cookie：

```text
Set-Cookie: ts_bui=...; Path=/s/{sandbox-name}/; HttpOnly; Secure; SameSite=Lax
```

5. 再跳转到：

```text
https://bui.treadstone-ai.dev/s/{sandbox-name}/
```

### Token 载荷建议

- `sandbox_id`
- `user_id`
- `exp`
- `type = "bui_token"`

### 为什么不直接继续用现有 sandbox token

可以复用现有签发能力，但建议逻辑上区分：

- `sandbox_token`：给 Agent / SDK / 编程调用
- `bui_token`：给浏览器入口与 BUI cookie exchange

原因：

- 语义清晰
- 生命周期可分离
- 便于未来单独收紧浏览器策略

## 6.5 路由设计

### HTTP

```text
GET|POST|PUT|PATCH|DELETE /s/{sandbox-name}/{path:path}
```

行为：

- 查 DB 得到 Sandbox
- 校验 ownership / BUI cookie
- 代理到 sandbox Pod 的 `/{path}`

根页面：

```text
GET /s/{sandbox-name}/
```

等价于代理：

```text
/index.html
```

### WebSocket

```text
WS /s/{sandbox-name}/{path:path}
```

行为与 HTTP 一致，只是上游使用 `ws://...`

## 6.6 必须补齐的请求头

向上游转发时至少补齐：

```text
X-Forwarded-Prefix: /s/{sandbox-name}
X-Forwarded-Host: bui.treadstone-ai.dev
X-Forwarded-Proto: https
```

必要时还应保留：

- `Origin`
- `Host`（如上游需要，可显式设置为上游 svc host 或浏览器 host，视兼容性测试结果决定）

## 6.7 必须补齐的响应重写

### Location 重写

将以下返回值重写到当前 BUI 前缀下：

- `Location: /foo`
- `Location: http://upstream/foo`
- `Location: https://bui.treadstone-ai.dev/foo`

统一重写为：

```text
Location: /s/{sandbox-name}/foo
```

### Set-Cookie Path 重写

若上游返回：

```text
Set-Cookie: key=val; Path=/
```

重写为：

```text
Set-Cookie: key=val; Path=/s/{sandbox-name}/
```

这样同一浏览器打开多个 Sandbox 时不会互相污染。

## 6.8 `urls.web` 的生成规则

### path 模式

```text
https://bui.treadstone-ai.dev/s/{sandbox-name}/
```

### subdomain 模式

```text
https://{sandbox-name}.bui.treadstone-ai.dev/
```

因此建议将当前 `urls.web` 生成从“读取 `request.base_url + sandbox_domain`”升级为“读取专门的 web config”。

---

## 7. 安全设计

### 7.1 当前安全缺口

现有 `SandboxSubdomainMiddleware` 只按 host 做转发，没有鉴权。

这在公网生产环境中意味着：

- 只要知道或猜到 sandbox host，就可能直接访问
- 绕过 control plane 的 owner 校验
- 绕过 API key / cookie / sandbox token 认证链路

### 7.2 新方案要求

- Browser UI 必须与 API 一样经过 owner 校验
- 浏览器 cookie 必须 sandbox 级隔离
- token 必须短时效
- 对外暴露的 Web UI URL 不应长期内嵌 bearer token

### 7.3 建议策略

- 生产环境禁用当前“无鉴权子域名 middleware”
- 本地开发可保留 `sandbox.localhost`
- 浏览器入口统一走 BUI Gateway

---

## 8. 迁移与落地步骤

### Phase 1：独立 Browser Host

1. 新增 `bui.treadstone-ai.dev` Ingress host
2. 使用单域名 TLS 证书
3. 不引入 wildcard DNS/TLS

### Phase 2：控制面 URL 生成

1. 新增 `sandbox_web_*` 配置
2. `urls.web` 改为输出 `bui.treadstone-ai.dev/s/{sandbox}/`

### Phase 3：BUI Auth

1. 新增 BUI token 签发
2. 新增 `/open/{sandbox}` token exchange
3. 新增 BUI cookie

### Phase 4：BUI HTTP + WS Proxy

1. 新增 path-based browser router
2. 补齐 `X-Forwarded-*`
3. 补齐 `Location` / `Set-Cookie` 重写

### Phase 5：验证

至少覆盖以下场景：

- `index.html` 可正常打开
- VNC 连接成功
- VS Code Terminal 连接成功
- Jupyter 页面可打开并执行
- 浏览器截图/控制接口正常
- 下载链接不丢前缀
- 多 Sandbox 并行打开，cookie 不串

### Phase 6：清理旧入口

- 生产上移除或显式关闭旧的无鉴权子域名入口
- 文档统一改为 `bui` 入口

---

## 9. 未来扩展

### 9.1 升级到 `*.bui`

如果未来接受 wildcard DNS/TLS，可无缝切到：

```text
https://{sandbox-name}.bui.treadstone-ai.dev/
```

此时：

- `X-Forwarded-Prefix` 与 `Location` 重写需求显著下降
- 浏览器兼容性更自然

但认证模型仍建议保留，不应退回到“仅按 host 透传”。

### 9.2 支持多入口并存

长期可同时支持：

- `path`：单域名、低成本
- `subdomain`：更自然的浏览器体验

由配置开关控制。

---

## 10. 风险与待确认项

1. AIO 首页修复后，是否仍有个别子服务未完全遵守 `X-Forwarded-Prefix`
2. code-server / Jupyter / noVNC 是否会返回需要额外改写的绝对 URL
3. 某些上游返回多个 `Set-Cookie` 时，当前响应封装是否需要特殊处理
4. 是否要将 `sandbox name` 暴露在 URL 中，还是统一用 `sandbox id`
5. BUI cookie 是否要按 sandbox path 隔离，或按 sandbox id 隔离

---

## 11. 推荐结论

**最终推荐：**

- 生产默认采用 **`https://bui.treadstone-ai.dev/s/{sandbox-name}/`**
- 新增 **BUI Gateway**，统一处理认证、WS、前缀、重定向与 cookie
- 保留 `*.bui.treadstone-ai.dev` 作为未来升级选项
- 生产环境不再直接暴露当前“无鉴权的 sandbox 子域名代理”

这条路线比“继续复用 `*.api.treadstone-ai.dev`”更清晰，也比“立刻购买通配符证书”更省成本；同时它保留了未来平滑切换到 wildcard 子域名模式的空间。

---

## 12. 参考资料

- agent-infra/sandbox Preview Proxy 文档：<https://sandbox.agent-infra.com/guide/basic/proxy>
- agent-infra/sandbox `v1.0.0.151` release：<https://github.com/agent-infra/sandbox/releases/tag/v1.0.0.151>
- agent-infra/sandbox `v1.0.0.152` release：<https://github.com/agent-infra/sandbox/releases/tag/v1.0.0.152>
- code-server 代理/子路径指南：<https://coder.com/docs/code-server/guide>
