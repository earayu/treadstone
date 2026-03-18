# Treadstone K8s 部署策略设计

> 日期：2026-03-18
>
> 状态：已批准

## 背景

Treadstone 进入 Phase 2（沙箱编排）后，需要在 K8s 上部署多个组件：

1. **Treadstone API** — FastAPI 应用服务
2. **agent-sandbox controller** — [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) 的 CRD + controller，管理 Sandbox 生命周期
3. **Sandbox Router** — 轻量级反向代理，将请求路由到对应的 Sandbox Pod
4. **Sandbox Resources** — SandboxTemplate / SandboxWarmPool 等 CR 实例定义
5. **agent-infra/sandbox** — 运行在 Sandbox Pod 内的 [All-in-One 容器镜像](https://github.com/agent-infra/sandbox)（Browser + Shell + File + MCP + VSCode）

其中 (5) 是 Docker 镜像，不需要独立部署，由 agent-sandbox controller 创建 Pod 时拉取。(1)-(4) 需要 K8s 部署方案。

## 调研结论

### agent-sandbox 上游安装方式

上游 kubernetes-sigs/agent-sandbox **没有官方 Helm chart**。安装方式是原始 manifest：

```bash
kubectl apply -f https://github.com/kubernetes-sigs/agent-sandbox/releases/download/v0.2.1/manifest.yaml
kubectl apply -f https://github.com/kubernetes-sigs/agent-sandbox/releases/download/v0.2.1/extensions.yaml
```

这是 K8s SIG 项目的典型做法（同 gateway-api、LWS 等）。

### 社区 Helm chart 调查

| 来源 | Chart 名称 | 说明 |
|---|---|---|
| **OpenKruise** ([openkruise/agents](https://github.com/openkruise/agents)) | `agents-sandbox-controller` v0.1.0 | **不是上游包装，是独立重写**。API Group `agents.kruise.io/v1alpha1` 与上游 `agents.x-k8s.io/v1alpha1` 不同，CRD 体系不兼容（用 SandboxSet 替代 SandboxTemplate + WarmPool）。不可直接使用。 |
| **Alibaba OpenSandbox** ([alibaba/OpenSandbox](https://github.com/alibaba/OpenSandbox)) | `opensandbox-controller` | 批量沙箱编排层（BatchSandbox + Pool），与 agent-sandbox 互补而非替代。可作为未来 RL 场景的增强选项。 |
| **UK AI Safety Institute** | `agent-env`（内置） | 面向 AI 安全评估场景，强依赖 Cilium + gVisor + NFS-CSI，不通用。 |
| **Artifact Hub 其他** | 无 | 没有其他第三方为上游 agent-sandbox 提供 Helm chart。 |

**结论：没有可直接复用的上游 Helm chart，需要自己包装。**

### Sandbox Router

agent-sandbox Python SDK 的通信架构依赖一个 [sandbox-router](https://github.com/kubernetes-sigs/agent-sandbox/tree/main/clients/python/agentic-sandbox-client/sandbox-router) 反向代理：

- 根据 `X-Sandbox-ID` header 将请求路由到对应 Sandbox Pod（通过 K8s 内部 DNS）
- FastAPI + Uvicorn 实现，需要自行 build Docker 镜像
- Treadstone API 作为 in-cluster 服务使用 Internal Mode 直连 `sandbox-router-svc`

## 设计决策

### 决策 1：统一使用 Helm chart 部署

所有 K8s 部署均使用 Helm chart，通过 `make deploy-*` 命令统一操作。

### 决策 2：3 个独立 Helm chart

按生命周期和权限边界拆分为 3 个 chart：

| Chart | 内容 | Namespace | 更新频率 | 权限 |
|---|---|---|---|---|
| `agent-sandbox` | controller + CRD + extensions | `agent-sandbox-system` | 极低（跟随上游 release） | cluster-admin |
| `treadstone-api` | FastAPI Deployment + Service + ConfigMap + ServiceAccount | `treadstone` | 高（每次功能迭代） | namespace |
| `sandbox-runtime` | Sandbox Router + SandboxTemplate CRs + WarmPool CRs | `treadstone` | 中（模板/路由变更时） | namespace |

拆分原因：
- **生命周期不同**：controller 装一次很少动，API 频繁更新，sandbox 运行时配置按需调整
- **失败隔离**：某个 chart 升级失败不影响其他
- **权限分离**：controller 需要 cluster-admin，其他只需 namespace 级权限
- **关注点分离**：sandbox-runtime 的 Router + Template + WarmPool 是沙箱运行时基础设施，逻辑内聚

### 决策 3：agent-sandbox controller 的包装策略 — Vendor + 薄 Helm 包装

不是把上游 manifest 拆碎成 Helm 模板（维护成本过高），而是：

1. `upstream/` 目录 git track 原始 manifest，原样保留
2. `templates/` 用 Helm 的 `.Files.Get` 加载原始 manifest，做少量参数化 patch
3. 升级流程：下载新版 manifest → 替换 `upstream/` → 更新 `VERSION` → `helm upgrade`

参数化覆盖范围：
- `namespace`
- `controller.image.registry`（支持阿里 ACR 镜像加速）
- `controller.resources`
- `controller.replicas`

### 决策 4：多环境差异化通过 values 文件

每个 chart 提供 `values.yaml`（默认）+ `values-dev.yaml`（Kind 本地）+ `values-prod.yaml`（ACK 生产）。

| 配置项 | dev (Kind) | prod (ACK) |
|---|---|---|
| Treadstone image | `treadstone-api:latest` | ACR registry |
| agent-sandbox controller image | `registry.k8s.io/...` | ACR mirror |
| agent-infra/sandbox image | `ghcr.io/agent-infra/sandbox:latest` | 中国镜像源或 ACR mirror |
| Treadstone replicas | 1 | 2+ |
| Controller replicas | 1 | 2 (HA) |
| Router replicas | 1 | 2 (HA) |
| WarmPool size | 1 | 3-5 |
| HPA | 关闭 | 按需开启 |

## 目录结构

```
deploy/
├── treadstone-api/                        # Treadstone FastAPI 服务
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values-dev.yaml
│   ├── values-prod.yaml
│   └── templates/
│       ├── _helpers.tpl
│       ├── deployment.yaml
│       ├── service.yaml
│       ├── configmap.yaml
│       └── serviceaccount.yaml
│
├── sandbox-runtime/                       # Sandbox Router + CR 资源
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values-dev.yaml
│   ├── values-prod.yaml
│   └── templates/
│       ├── _helpers.tpl
│       ├── router-deployment.yaml         # sandbox-router 反向代理
│       ├── router-service.yaml
│       ├── sandbox-templates.yaml         # SandboxTemplate CRs
│       └── sandbox-warmpool.yaml          # SandboxWarmPool CR
│
└── agent-sandbox/                         # 上游 controller Helm 包装
    ├── Chart.yaml
    ├── values.yaml
    ├── values-dev.yaml
    ├── values-prod.yaml
    ├── upstream/                           # Vendor 的原始 manifest
    │   ├── manifest.yaml                  # v0.2.1 核心 CRD + controller
    │   ├── extensions.yaml                # v0.2.1 extensions
    │   └── VERSION                        # "v0.2.1"
    └── templates/
        ├── _helpers.tpl
        ├── namespace.yaml
        └── upstream-resources.yaml
```

## 通信链路

```
用户/Agent
  │
  ▼
Treadstone API (FastAPI, deploy/treadstone-api)
  │
  ├─ 创建/删除沙箱 ──▶ K8s API ──▶ agent-sandbox controller
  │                                      │
  │                                      ▼
  │                              Sandbox Pod (agent-infra/sandbox)
  │                                      ▲
  ├─ 操作沙箱 (Shell/Browser/File) ─▶ sandbox-router-svc:8080
  │                    (X-Sandbox-ID header routing)
  │
  └─ 查询状态 ──▶ K8s API ──▶ 读 Sandbox CR status
```

## Makefile 命令

```makefile
# ENV 默认 dev，可用 dev / prod
ENV ?= dev

deploy-infra:      ## Deploy agent-sandbox controller (once per cluster)
deploy-runtime:    ## Deploy sandbox router + templates + warmpool
deploy-app:        ## Deploy Treadstone API
deploy-all:        ## Deploy everything (infra → runtime → app)
undeploy-app:      ## Undeploy Treadstone API
undeploy-runtime:  ## Undeploy sandbox runtime
undeploy-all:      ## Undeploy everything
```

用法：

```bash
# 首次搭建整个环境
make deploy-all ENV=dev

# 日常开发只更新 API
make deploy-app ENV=dev

# 调整沙箱模板或预热池
make deploy-runtime ENV=dev

# 生产部署
make deploy-all ENV=prod
```

## 升级 agent-sandbox controller 流程

```bash
# 1. 下载新版 manifest
export VERSION=v0.3.0
curl -Lo deploy/agent-sandbox/upstream/manifest.yaml \
  https://github.com/kubernetes-sigs/agent-sandbox/releases/download/${VERSION}/manifest.yaml
curl -Lo deploy/agent-sandbox/upstream/extensions.yaml \
  https://github.com/kubernetes-sigs/agent-sandbox/releases/download/${VERSION}/extensions.yaml
echo "${VERSION}" > deploy/agent-sandbox/upstream/VERSION

# 2. Review diff
git diff deploy/agent-sandbox/upstream/

# 3. 升级
make deploy-infra ENV=dev

# 4. 验证
kubectl get pods -n agent-sandbox-system

# 5. 提交
git add deploy/agent-sandbox/upstream/
git commit -m "chore: upgrade agent-sandbox to ${VERSION}"
```

## 未来扩展

- **OpenSandbox 集成**：如果未来需要批量沙箱（RL 训练场景），可以新增 `deploy/opensandbox/` chart 引入 alibaba/OpenSandbox 的 BatchSandbox + Pool 能力，与现有 agent-sandbox 互补
- **GitOps**：`deploy/` 目录结构天然适配 ArgoCD / Flux，每个 chart 对应一个 Application CR
- **CI/CD**：GitHub Actions 中按 chart 变更范围触发对应的 deploy job
