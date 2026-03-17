# Treadstone 设计文档

## 愿景

构建一个开源平台，将 sandbox + skills 组合为可复用的垂直 Agent，并形成 marketplace。填补当前生态在 Layer 4（Agent 市场与编排平台）的空白。

## 核心概念

- **Sandbox Template**：预配置的沙箱环境模板（Python 数据科学、Node.js Web 开发、Linux DevOps…）
- **Skill Pack**：一组工具/能力定义（MCP server、函数、prompt）
- **Agent = Sandbox Template + Skill Pack**：组合产出一个垂直 Agent
- **Marketplace**：开发者发布 Sandbox Template 和 Skill Pack，用户自由组合

## 架构

```
┌─────────────────────────────────────────────────────┐
│                  Treadstone Platform API             │
│          (业务层：注册/登录/付款/marketplace)          │
├─────────────────────────────────────────────────────┤
│              Sandbox Orchestration Layer             │
│         kubernetes-sigs/agent-sandbox (CRD)         │
│                                                     │
│  SandboxTemplate  SandboxClaim  SandboxWarmPool     │
├─────────────────────────────────────────────────────┤
│              Sandbox Runtime Layer                   │
│            agent-infra/sandbox (Docker)              │
│                                                     │
│  Browser(VNC)  Shell  FileSystem  MCP Hub  VSCode   │
├─────────────────────────────────────────────────────┤
│              Isolation Layer (K8s RuntimeClass)      │
│                gVisor — 默认隔离后端                  │
└─────────────────────────────────────────────────────┘
```

## 技术选型

| 层面 | 选型 | 理由 |
|---|---|---|
| 语言 | Python 3.12+ | 与 agent-sandbox SDK 和 agent-infra SDK 对齐 |
| Web 框架 | FastAPI | OpenAPI 自动生成，async 原生支持 |
| API 规范 | OpenAPI (FastAPI 自动生成) | 标准化接口 |
| 包管理 | uv | 快速，现代 Python 工具链 |
| ASGI 服务器 | Uvicorn | FastAPI 标配 |
| 异步任务 | FastAPI BackgroundTasks | MVP 阶段够用，K8s 本身已是异步 |
| 数据库 | PostgreSQL | 用户/订单/沙箱元数据 |
| K8s 交互 | agent-sandbox Python SDK | 封装在 k8s_client.py 中 |
| 隔离层 | gVisor (RuntimeClass) | 不需裸金属/嵌套虚拟化，运维成本最低 |
| 容器化 | Docker + K8s Helm Chart | 参考 ApeRAG 部署方式 |

### 不引入的技术（MVP 阶段）

| 技术 | 不引入的理由 |
|---|---|
| Celery + Redis | K8s 本身已是异步编排，FastAPI BackgroundTasks 够用 |
| Redis 缓存 | 沙箱状态在 K8s CR 中，无需额外缓存 |
| 前端 | 一个人精力有限，先出 API，用 Swagger UI 演示 |
| OpenSandbox | MVP 阶段两个项目已够用，后期可选引入 |

## 关键设计决策

1. **编排层选 kubernetes-sigs/agent-sandbox**：K8s 社区官方标准方向，CRD 模式与 KubeBlocks 经验一致。
2. **运行时层选 agent-infra/sandbox**：All-in-One 容器（Browser/Shell/File/MCP/VSCode），能力最全面。
3. **隔离层选 gVisor**：不需要嵌套虚拟化，在云厂商普通 VM 节点即可运行，配置简单。
4. **不引入 OpenSandbox**：避免与 agent-sandbox 在编排层重叠，减少集成复杂度。后期如需多语言 SDK 或 BatchSandbox 可选引入。
5. **k8s_client.py 作为适配层**：所有 K8s 交互封装在此，未来换编排层只改一个文件。

## 部署目标

- 部署在 K8s 集群上（云厂商托管 K8s：GKE/EKS/AKS）
- 开发环境用 Docker Compose + Kind/Minikube

## 日期

2026-03-17
