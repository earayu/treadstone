# Treadstone

Sandbox + Skills 组合为可复用垂直 Agent 的开放平台与市场。

## 愿景

当前 AI Agent 沙箱生态已形成 5 层架构（隔离原语 → 运行时/SDK → 平台服务 → 专项沙箱 → Agent 市场），但缺少一个将 **sandbox + skills 组合为可复用垂直 Agent** 并形成 marketplace 的开放平台。Treadstone 填补这一空白。

## 核心概念

- **Sandbox Template** — 预配置的沙箱环境模板
- **Skill Pack** — 一组工具/能力定义（MCP server、函数、prompt）
- **Agent = Template + Skills** — 组合产出一个垂直 Agent
- **Marketplace** — 开发者发布 Template 和 Skill Pack，用户自由组合

## 架构

```
┌─────────────────────────────────────────────────┐
│            Treadstone Platform API               │
├─────────────────────────────────────────────────┤
│         Sandbox Orchestration Layer              │
│       kubernetes-sigs/agent-sandbox (CRD)        │
├─────────────────────────────────────────────────┤
│          Sandbox Runtime Layer                   │
│        agent-infra/sandbox (Docker)              │
├─────────────────────────────────────────────────┤
│           Isolation Layer                        │
│         gVisor (K8s RuntimeClass)                │
└─────────────────────────────────────────────────┘
```

## 技术栈

- **后端**: Python 3.12+, FastAPI, SQLAlchemy async
- **数据库**: [Neon](https://neon.tech) (Serverless PostgreSQL)
- **包管理**: uv
- **沙箱编排**: [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox)
- **沙箱运行时**: [agent-infra/sandbox](https://github.com/agent-infra/sandbox)
- **隔离层**: gVisor

## 开发

```bash
make help             # 查看所有可用命令
make dev              # 启动本地开发服务器 (热重载)
make test             # 运行测试
make lint             # 代码检查
make format           # 自动格式化
make migrate          # 运行数据库迁移
make migration MSG=x  # 生成新迁移
make build            # 构建 Docker 镜像
```

## 状态

项目处于早期设计阶段。详见 [docs/plans/](docs/zh-CN/plans/) 目录中的设计文档和实施计划。

## License

[Apache License 2.0](LICENSE)
