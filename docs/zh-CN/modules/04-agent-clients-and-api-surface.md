# 模块 4：Agent 接入面：API、CLI 与 Python SDK

## 模块目标

Treadstone 当前仓库并没有完整的 Web 控制台应用，但已经稳定提供三种 agent-friendly 接入面：

- REST API
- CLI
- Python SDK

这个模块描述这些接入面的组织方式，以及当前仓库里真正可用的自动化登录流程。

## 1. REST API 是源头

当前所有对外能力都先落在 FastAPI 路由上，再生成 OpenAPI 和 SDK。

主路由标签包括：

- `auth`
- `sandboxes`
- `browser`
- `usage`
- `admin`
- `audit`
- `config`
- `system`

OpenAPI 的 unique id 规则在 `main.py` 中固定为：

- `"{tag}-{route_name}"`

这样做的目的是让生成出来的 SDK 方法名更稳定。

## 2. CLI

CLI 代码位于 `cli/treadstone_cli/`，当前面向用户和 agent 都是一级产品接口。现有命令分组包括：

- `system`
- `auth`
- `sandboxes`
- `templates`
- `api-keys`
- `config`
- `guide`

CLI 的当前设计重点不是“交互式花哨界面”，而是：

- 默认命令适合人类操作
- `--json` 输出适合 agent 链式调用
- `guide agent` 和 `--skills` 可以直接把内置说明暴露给代理

## 3. Python SDK

Python SDK 位于 `sdk/python/`，由 OpenAPI 生成，当前已经纳入仓库。

它适合：

- Python 自动化脚本
- 更严格的类型约束
- 直接把控制面接口嵌入 agent runtime

当前仓库里的 SDK 形态是“生成产物”，因此：

- 具体方法以生成后的模块为准
- 接口命名以 OpenAPI tag 和路由名为准

## 4. CLI 浏览器登录流

除了普通邮箱密码登录以外，仓库里还实现了一套给 CLI 用的浏览器授权流。

### 关键对象

- `CliLoginFlow`
- `flow_id`
- `flow_secret`
- `browser_url`
- `session_token`

### 对外接口

- `POST /v1/auth/cli/flows`
- `GET /v1/auth/cli/flows/{flow_id}/status`
- `POST /v1/auth/cli/flows/{flow_id}/exchange`

### 浏览器侧页面

- `GET /v1/auth/cli/login`
- `POST /v1/auth/cli/login`

### 当前流程

1. CLI 创建一个 flow
2. 服务端返回 `flow_id`、`flow_secret`、`browser_url`
3. 用户在浏览器里打开登录页，用邮箱密码或 OAuth 登录
4. flow 状态变为 `approved`
5. CLI 轮询状态
6. CLI 用 `flow_secret` 换取 `session_token`
7. flow 最终转为 `used`

这套能力是当前代码真实存在的，不再需要参考旧的 “Phase 3 SDK/CLI 实施计划”。

## 5. 当前推荐接入方式

### 对 agent

推荐顺序：

1. CLI `--json`
2. 直接调用 REST API
3. Python SDK

原因很简单：

- CLI 已经把输出和错误做了 agent-friendly 处理
- REST API 是真实 source of truth
- SDK 更适合 Python 生态，但更新频率受 OpenAPI 生成流程影响

### 对人类

推荐顺序：

1. CLI
2. 浏览器登录页 / Web hand-off
3. 直接 API 调试

## 6. 当前边界

- 当前仓库没有独立前端控制台项目，因此“Web UI”不应再被写成一个已经实现的客户端产品
- TypeScript types 和前端页面设计不再作为主文档结构中心
- Agent 接入面的真实核心是：**API contract + CLI + generated SDK**

