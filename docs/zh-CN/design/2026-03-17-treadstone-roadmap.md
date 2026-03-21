# Treadstone Roadmap

## Phase 0：项目脚手架（第 1 周）

搭建项目基础结构，能本地启动 FastAPI 服务，连接 PostgreSQL，跑通一个健康检查接口。

- 初始化 uv 项目，配置 pyproject.toml
- FastAPI 应用骨架 + Uvicorn
- Neon (Serverless PostgreSQL) 连接 + SQLAlchemy async
- Dockerfile + K8s Manifests
- 基础 CI（lint + test）

## Phase 1：认证系统（第 2 周）

用户注册、登录、JWT 鉴权。Marketplace 的一切都建立在用户体系之上。

- 用户数据模型（User table）
- 注册 / 登录 API
- JWT 签发与验证中间件
- API 路由鉴权装饰器

## Phase 2：核心沙箱编排（第 3-4 周）⭐ 核心

这是整个平台的技术核心。在 K8s 上通过 agent-sandbox CRD 创建和管理沙箱，Pod 内运行 agent-infra/sandbox 镜像。

- 搭建开发 K8s 环境（Kind/Minikube + gVisor RuntimeClass）
- 安装 agent-sandbox controller
- k8s_client.py 适配层：封装 agent-sandbox Python SDK
- SandboxTemplate CRD 管理（预置模板：Python/Node.js/Linux）
- 沙箱 CRUD API：创建（SandboxClaim）、查询状态、获取端点、销毁
- 沙箱生命周期管理：超时自动清理、健康检查
- WarmPool 配置：预热沙箱加速分配

## Phase 3：付款与计量（第 5 周）

按用量计费的基础。先集成 Stripe，后续可换。

- 沙箱使用时长计量（创建时间 → 销毁时间）
- Stripe 集成：支付意向、webhook 处理
- 用户余额/配额模型
- 用量超限自动停止沙箱

## Phase 4：Sandbox Template + Skill Pack 市场（第 6-7 周）

平台的差异化能力——让开发者发布模板和技能包，用户自由组合。

- Sandbox Template 数据模型与 API（发布/搜索/版本管理）
- Skill Pack 数据模型与 API（MCP 兼容格式）
- 组合引擎：Template + Skills → 生成 SandboxClaim 配置
- 基础 Marketplace API：列表、搜索、评分

## Phase 5：生产化（第 8 周+）

从 MVP 走向可用的生产服务。

- Helm Chart 打包
- K8s 生产集群部署（GKE/EKS/AKS）
- 日志/监控/告警（OpenTelemetry）
- API 限流与安全加固
- 前端 Web UI

---

## 里程碑

| 里程碑 | 时间 | 交付物 |
|---|---|---|
| M0：能跑起来 | 第 1 周末 | FastAPI + Neon PostgreSQL 运行 |
| M1：能登录 | 第 2 周末 | 注册/登录/JWT 全流程 |
| M2：能创建沙箱 | 第 4 周末 | 通过 API 在 K8s 上创建/使用/销毁沙箱 |
| M3：能收钱 | 第 5 周末 | Stripe 集成，按时长计费 |
| M4：能组合 Agent | 第 7 周末 | Template + Skills 组合，Marketplace API |
| M5：能上线 | 第 8 周+ | Helm 部署，生产集群运行 |

## 日期

2026-03-17
