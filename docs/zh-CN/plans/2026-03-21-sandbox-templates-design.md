# Sandbox Templates 多规格设计

**日期：** 2026-03-21

**目标：** 将单一 SandboxTemplate 扩展为 5 级规格体系（tiny/small/medium/large/xlarge），统一使用 AIO 镜像，通过资源配额区分用途，并为每个规格配备可选的 WarmPool 预热池。

---

## 1. 背景

### 1.1 现状

当前 Helm chart（`deploy/sandbox-runtime/`）只部署一个 SandboxTemplate（`treadstone-sandbox`），使用 `agent-infra/sandbox` AIO 镜像，固定资源配额（250m CPU / 512Mi 内存）。

### 1.2 问题

- **无法区分场景**：轻量级代码执行和重度开发环境使用相同资源，要么浪费资源，要么资源不足
- **README 愿景未兑现**：README 承诺了 Code Runner（轻量）和 AIO（全功能）两种模板，实际只有一种
- **agent-sandbox CRD 约束**：`SandboxClaim` 不支持覆盖资源配额（只有 `templateRef` + `lifecycle`），不同规格必须通过不同 SandboxTemplate 实现

### 1.3 调研结论

- **统一镜像**：`agent-infra/sandbox` AIO 镜像不支持通过环境变量关闭浏览器/VNC/Jupyter 等组件，但资源限制可以有效控制实际开销。镜像只拉一次，多模板共享磁盘缓存
- **不另建镜像**：自建轻量镜像需要额外维护 HTTP API 兼容层，MVP 阶段 ROI 不高
- **竞品参考**：Daytona 和 E2B 均提供多规格选择（small/medium/large），用户按需选择

---

## 2. 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 镜像策略 | 统一 AIO 镜像 | 一次拉取、API 兼容、零额外维护 |
| 规格数量 | 5 级（tiny/small/medium/large/xlarge） | 覆盖从代码片段到重度工作负载的全场景 |
| CPU:Memory 比 | 1:2 | 代码执行场景 CPU 密集，3 台 16c/32GB 服务器利用率最优 |
| 命名规则 | `aio-sandbox-{size}` | 统一前缀，便于识别和 API 过滤 |
| WarmPool 默认策略 | 仅 tiny 开启（1 副本） | tiny 是最常用的轻量场景，预热收益最大；其他规格按需开启 |
| Helm 结构 | `sandboxTemplates` 数组 | 循环渲染，新增规格只改 values.yaml |

---

## 3. 规格详情

| Template | display_name | CPU requests | CPU limits | Memory requests | Memory limits | WarmPool |
|----------|-------------|-------------|-----------|----------------|--------------|----------|
| `aio-sandbox-tiny` | AIO Sandbox Tiny | 250m | 500m | 512Mi | 1Gi | 开启（1 副本） |
| `aio-sandbox-small` | AIO Sandbox Small | 500m | 1 | 1Gi | 2Gi | 关闭 |
| `aio-sandbox-medium` | AIO Sandbox Medium | 1 | 2 | 2Gi | 4Gi | 关闭 |
| `aio-sandbox-large` | AIO Sandbox Large | 2 | 4 | 4Gi | 8Gi | 关闭 |
| `aio-sandbox-xlarge` | AIO Sandbox XLarge | 4 | 8 | 8Gi | 16Gi | 关闭 |

### 3.1 Limits = 2x Requests

所有规格的 limits 均为 requests 的 2 倍。这允许突发使用（burstable QoS），同时防止单个 Sandbox 过度占用节点资源。

### 3.2 集群容量估算（3 台 16c/32GB）

假设每台节点预留 2c/4GB 给系统组件（kubelet、agent-sandbox controller、Treadstone 等）：

| 规格 | 单节点可调度（按 requests） | 集群总计 |
|------|--------------------------|---------|
| tiny | ~56 个 | ~168 个 |
| small | ~28 个 | ~84 个 |
| medium | ~14 个 | ~42 个 |
| large | ~7 个 | ~21 个 |
| xlarge | ~3 个 | ~9 个 |

实际数量取决于混合调度情况。

---

## 4. Helm Chart 改造

### 4.1 values.yaml 新结构

从 `sandboxTemplate`（单数）改为 `sandboxTemplates`（数组），`image` 和 `containerPort` 提升为全局字段：

```yaml
image: ghcr.io/agent-infra/sandbox:latest
containerPort: 8080

sandboxTemplates:
  - name: aio-sandbox-tiny
    displayName: "AIO Sandbox Tiny"
    description: "Lightweight sandbox for code execution and scripting"
    cpu: { requests: "250m", limits: "500m" }
    memory: { requests: "512Mi", limits: "1Gi" }
    warmPool: { enabled: true, replicas: 1 }

  - name: aio-sandbox-small
    displayName: "AIO Sandbox Small"
    description: "Small sandbox for simple development tasks"
    cpu: { requests: "500m", limits: "1" }
    memory: { requests: "1Gi", limits: "2Gi" }
    warmPool: { enabled: false, replicas: 1 }

  - name: aio-sandbox-medium
    displayName: "AIO Sandbox Medium"
    description: "General-purpose development environment"
    cpu: { requests: "1", limits: "2" }
    memory: { requests: "2Gi", limits: "4Gi" }
    warmPool: { enabled: false, replicas: 1 }

  - name: aio-sandbox-large
    displayName: "AIO Sandbox Large"
    description: "Full-featured sandbox with browser automation"
    cpu: { requests: "2", limits: "4" }
    memory: { requests: "4Gi", limits: "8Gi" }
    warmPool: { enabled: false, replicas: 1 }

  - name: aio-sandbox-xlarge
    displayName: "AIO Sandbox XLarge"
    description: "Heavy workloads with maximum resources"
    cpu: { requests: "4", limits: "8" }
    memory: { requests: "8Gi", limits: "16Gi" }
    warmPool: { enabled: false, replicas: 1 }
```

### 4.2 sandbox-templates.yaml（循环渲染）

```yaml
{{- range .Values.sandboxTemplates }}
---
apiVersion: extensions.agents.x-k8s.io/v1alpha1
kind: SandboxTemplate
metadata:
  name: {{ .name }}
  namespace: {{ $.Release.Namespace }}
  labels:
    {{- include "sandbox-runtime.labels" $ | nindent 4 }}
  annotations:
    display-name: {{ .displayName | quote }}
    description: {{ .description | quote }}
spec:
  podTemplate:
    spec:
      containers:
        - name: sandbox
          image: {{ $.Values.image }}
          ports:
            - containerPort: {{ $.Values.containerPort }}
          readinessProbe:
            tcpSocket:
              port: {{ $.Values.containerPort }}
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            tcpSocket:
              port: {{ $.Values.containerPort }}
            initialDelaySeconds: 15
            periodSeconds: 10
          resources:
            requests:
              cpu: {{ .cpu.requests | quote }}
              memory: {{ .memory.requests | quote }}
            limits:
              cpu: {{ .cpu.limits | quote }}
              memory: {{ .memory.limits | quote }}
      restartPolicy: OnFailure
{{- end }}
```

### 4.3 sandbox-warmpool.yaml（循环渲染）

```yaml
{{- range .Values.sandboxTemplates }}
{{- if .warmPool.enabled }}
---
apiVersion: extensions.agents.x-k8s.io/v1alpha1
kind: SandboxWarmPool
metadata:
  name: {{ .name }}-pool
  namespace: {{ $.Release.Namespace }}
  labels:
    {{- include "sandbox-runtime.labels" $ | nindent 4 }}
spec:
  replicas: {{ .warmPool.replicas }}
  sandboxTemplateRef:
    name: {{ .name }}
{{- end }}
{{- end }}
```

---

## 5. 联动更新

| 文件 | 变更 |
|------|------|
| `deploy/sandbox-runtime/values.yaml` | 新结构（5 模板数组） |
| `deploy/sandbox-runtime/values-local.yaml` | 同步新结构（可使用国内镜像） |
| `deploy/sandbox-runtime/values-prod.yaml` | 同步新结构 |
| `deploy/sandbox-runtime/templates/sandbox-templates.yaml` | range 循环 |
| `deploy/sandbox-runtime/templates/sandbox-warmpool.yaml` | range 循环 |
| `treadstone/services/k8s_client.py` — `FakeK8sClient._DEFAULT_TEMPLATES` | 更新为 5 个模板 |
| `tests/api/test_sandbox_templates_api.py` | 断言数量和名称 |
| `README.md` | 更新 Sandbox Templates 章节 |

### 5.1 API 层

**无需改动。** `list_sandbox_templates` 已从 K8s 动态读取 SandboxTemplate CR，5 个模板会自动返回。创建 Sandbox 时 `"template": "aio-sandbox-tiny"` 直接引用模板名。

---

## 6. 与 Phase 2 设计的关系

Phase 2 设计文档中 `sandbox-templates` 相关内容保持不变：

- 模板仍为只读（Phase 4 Marketplace 时开放 CRUD）
- 数据来源仍为 K8s SandboxTemplate CR
- API 响应格式不变（`runtime_type` 全部为 `"aio"`）
- 创建 Sandbox 时的 `template` 字段引用模板名，规格由模板定义

---

## 7. 未来演进

| 方向 | 说明 |
|------|------|
| 自定义镜像 | 当 AIO 支持环境变量关闭组件时，tiny 可关闭浏览器/VNC 进一步降低资源 |
| GPU 规格 | 新增 `aio-sandbox-gpu` 模板，需要 GPU 节点池 |
| 自动缩放 WarmPool | 根据使用量动态调整 WarmPool replicas |
| 用户自定义规格 | Phase 4 Marketplace 允许用户创建自定义 SandboxTemplate |
