# Sandbox Templates Multi-Tier Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the single SandboxTemplate with 5-tier templates (tiny/small/medium/large/xlarge) using a unified AIO image, with per-template WarmPool support.

**Architecture:** Helm chart `deploy/sandbox-runtime/` restructured from single-template to array-based rendering. `FakeK8sClient` updated to match. All existing tests and E2E flows remain compatible since they use dynamic template names.

**Tech Stack:** Helm templates (Go templating), Python (SQLAlchemy, FastAPI), pytest, Hurl

---

### Task 1: Restructure Helm values.yaml files

**Files:**
- Modify: `deploy/sandbox-runtime/values.yaml`
- Modify: `deploy/sandbox-runtime/values-local.yaml`
- Modify: `deploy/sandbox-runtime/values-prod.yaml`
- Modify: `deploy/sandbox-runtime/values-demo.yaml`

**Step 1: Rewrite `values.yaml`**

Replace the current single-template structure:

```yaml
# Old structure (remove entirely)
sandboxTemplate:
  name: treadstone-sandbox
  image: ghcr.io/agent-infra/sandbox:latest
  containerPort: 8080
  resources:
    requests:
      cpu: 250m
      memory: 512Mi
      ephemeral-storage: 512Mi

warmPool:
  enabled: false
  replicas: 1
```

With the new array-based structure:

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

**Step 2: Rewrite `values-local.yaml`**

Same 5-template structure but with China mirror image:

```yaml
image: enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:latest
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

**Step 3: Rewrite `values-prod.yaml`**

Same structure, GHCR image, WarmPool replicas = 3 for tiny:

```yaml
image: ghcr.io/agent-infra/sandbox:latest
containerPort: 8080

sandboxTemplates:
  - name: aio-sandbox-tiny
    displayName: "AIO Sandbox Tiny"
    description: "Lightweight sandbox for code execution and scripting"
    cpu: { requests: "250m", limits: "500m" }
    memory: { requests: "512Mi", limits: "1Gi" }
    warmPool: { enabled: true, replicas: 3 }

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

**Step 4: Rewrite `values-demo.yaml`**

Same as `values.yaml` (default image, only tiny WarmPool enabled):

```yaml
image: ghcr.io/agent-infra/sandbox:latest
containerPort: 8080

sandboxTemplates:
  - name: aio-sandbox-tiny
    displayName: "AIO Sandbox Tiny"
    description: "Lightweight sandbox for code execution and scripting"
    cpu: { requests: "250m", limits: "500m" }
    memory: { requests: "512Mi", limits: "1Gi" }
    warmPool: { enabled: false, replicas: 1 }

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

**Step 5: Commit**

```bash
git add deploy/sandbox-runtime/values*.yaml
git commit -m "feat: restructure sandbox-runtime values to 5-tier template array"
```

---

### Task 2: Update Helm templates to loop over sandboxTemplates

**Files:**
- Modify: `deploy/sandbox-runtime/templates/sandbox-templates.yaml`
- Modify: `deploy/sandbox-runtime/templates/sandbox-warmpool.yaml`

**Step 1: Rewrite `sandbox-templates.yaml`**

Replace the entire file with a range loop. The key changes:
- `range .Values.sandboxTemplates` iterates all templates
- `$.Values.image` and `$.Values.containerPort` use `$` to reference root context inside range
- `annotations` carry `display-name` and `description` for the K8s client to read
- Resources use the new nested `cpu.requests`/`cpu.limits`/`memory.requests`/`memory.limits` structure

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

**Step 2: Rewrite `sandbox-warmpool.yaml`**

Replace the entire file with a range loop that conditionally renders each WarmPool:

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

**Step 3: Commit**

```bash
git add deploy/sandbox-runtime/templates/sandbox-templates.yaml deploy/sandbox-runtime/templates/sandbox-warmpool.yaml
git commit -m "feat: update Helm templates to render multi-tier sandbox templates"
```

---

### Task 3: Update FakeK8sClient default templates

**Files:**
- Modify: `treadstone/services/k8s_client.py` — `FakeK8sClient._DEFAULT_TEMPLATES`

**Step 1: Write the failing test**

In `tests/unit/test_k8s_client.py`, the existing test `test_list_sandbox_templates` checks for `python-dev` and `nodejs-dev`. Update it to check for the new 5 template names:

```python
async def test_list_sandbox_templates():
    client = FakeK8sClient()
    templates = await client.list_sandbox_templates("treadstone")
    assert len(templates) == 5
    names = [t["name"] for t in templates]
    assert "aio-sandbox-tiny" in names
    assert "aio-sandbox-small" in names
    assert "aio-sandbox-medium" in names
    assert "aio-sandbox-large" in names
    assert "aio-sandbox-xlarge" in names
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_k8s_client.py::test_list_sandbox_templates -v
```

Expected: FAIL — `"aio-sandbox-tiny"` not in names (still has `python-dev`, `nodejs-dev`).

**Step 3: Update `_DEFAULT_TEMPLATES` in `treadstone/services/k8s_client.py`**

Replace the 2-element tuple with 5 entries matching the new template names:

```python
_DEFAULT_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "name": "aio-sandbox-tiny",
        "display_name": "AIO Sandbox Tiny",
        "description": "Lightweight sandbox for code execution and scripting",
        "runtime_type": "aio",
        "resource_spec": {"cpu": "250m", "memory": "512Mi"},
    },
    {
        "name": "aio-sandbox-small",
        "display_name": "AIO Sandbox Small",
        "description": "Small sandbox for simple development tasks",
        "runtime_type": "aio",
        "resource_spec": {"cpu": "500m", "memory": "1Gi"},
    },
    {
        "name": "aio-sandbox-medium",
        "display_name": "AIO Sandbox Medium",
        "description": "General-purpose development environment",
        "runtime_type": "aio",
        "resource_spec": {"cpu": "1", "memory": "2Gi"},
    },
    {
        "name": "aio-sandbox-large",
        "display_name": "AIO Sandbox Large",
        "description": "Full-featured sandbox with browser automation",
        "runtime_type": "aio",
        "resource_spec": {"cpu": "2", "memory": "4Gi"},
    },
    {
        "name": "aio-sandbox-xlarge",
        "display_name": "AIO Sandbox XLarge",
        "description": "Heavy workloads with maximum resources",
        "runtime_type": "aio",
        "resource_spec": {"cpu": "4", "memory": "8Gi"},
    },
)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_k8s_client.py::test_list_sandbox_templates -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add treadstone/services/k8s_client.py tests/unit/test_k8s_client.py
git commit -m "feat: update FakeK8sClient with 5-tier sandbox templates"
```

---

### Task 4: Update template-related tests

**Files:**
- Modify: `tests/api/test_sandbox_templates_api.py`
- Modify: `tests/unit/test_k8s_client.py` (remaining references to `python-dev`)
- Modify: `tests/unit/test_sandbox_service.py`
- Modify: `tests/api/test_sandboxes_api.py`
- Modify: `tests/api/test_sandbox_proxy_api.py`
- Modify: `tests/api/test_sandbox_token_api.py`
- Modify: `tests/unit/test_k8s_sync.py`

**Step 1: Update `test_sandbox_templates_api.py`**

Change assertions from `python-dev` to `aio-sandbox-tiny` and count from `>= 2` to `>= 5`:

```python
async def test_list_templates_returns_items(auth_client):
    resp = await auth_client.get("/v1/sandbox-templates")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) >= 5
    names = [t["name"] for t in data["items"]]
    assert "aio-sandbox-tiny" in names
```

**Step 2: Update all `"python-dev"` references in test files**

In all test files listed above, replace `"python-dev"` with `"aio-sandbox-tiny"` (the default/smallest template). This is a simple find-and-replace in each file. The template name is only used as a reference string in test payloads — the actual behavior doesn't depend on the name.

Files and the replacements:

- `tests/unit/test_k8s_client.py`: `"python-dev"` → `"aio-sandbox-tiny"` (in `create_sandbox_claim` calls)
- `tests/unit/test_sandbox_service.py`: `"python-dev"` → `"aio-sandbox-tiny"` (in service test fixtures and assertions)
- `tests/api/test_sandboxes_api.py`: `"python-dev"` → `"aio-sandbox-tiny"` (in POST `/v1/sandboxes` payloads)
- `tests/api/test_sandbox_proxy_api.py`: `"python-dev"` → `"aio-sandbox-tiny"` (in POST `/v1/sandboxes` payloads)
- `tests/api/test_sandbox_token_api.py`: `"python-dev"` → `"aio-sandbox-tiny"` (in POST `/v1/sandboxes` payloads)
- `tests/unit/test_k8s_sync.py`: `"python-dev"` → `"aio-sandbox-tiny"` (in fixture data and claim calls)

**Step 3: Run full test suite**

```bash
make test
```

Expected: all tests PASS

**Step 4: Commit**

```bash
git add tests/
git commit -m "test: update all template references to aio-sandbox-tiny"
```

---

### Task 5: Update README.md

**Files:**
- Modify: `README.md`

**Step 1: Update the Sandbox Templates section**

Replace the current Code Runner / AIO section with the 5-tier table:

```markdown
## Sandbox Templates

Treadstone ships with five built-in size tiers — all powered by the same
AIO (All-in-One) image with different resource allocations.

| Template | CPU | Memory | Use Case |
|----------|-----|--------|----------|
| `aio-sandbox-tiny` | 0.25 core | 512 Mi | Code execution, script running |
| `aio-sandbox-small` | 0.5 core | 1 Gi | Simple development tasks |
| `aio-sandbox-medium` | 1 core | 2 Gi | General-purpose development |
| `aio-sandbox-large` | 2 cores | 4 Gi | Full-featured + browser automation |
| `aio-sandbox-xlarge` | 4 cores | 8 Gi | Heavy workloads |

```bash
# Quick code execution with the smallest footprint
treadstone run --template aio-sandbox-tiny "import math; print(math.pi)"

# Full development environment
treadstone create --template aio-sandbox-large --persist
```
```

Also update the Quick Start section to use `aio-sandbox-tiny` instead of `aio`:

```markdown
## Quick Start

```bash
# Execute code in a disposable sandbox
treadstone run "print('hello world')"

# Create a persistent development environment
treadstone create --template aio-sandbox-large --persist

# Run a command inside an existing sandbox
treadstone exec sb-3f8a -- npm install && npm test

# Check sandbox status
treadstone status sb-3f8a

# Tear it down
treadstone destroy sb-3f8a
```
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README with 5-tier sandbox templates"
```

---

### Task 6: Run full validation

**Step 1: Run linter**

```bash
make lint
```

Expected: PASS

**Step 2: Run full test suite**

```bash
make test
```

Expected: all tests PASS

**Step 3: Verify Helm template rendering**

```bash
helm template test-release deploy/sandbox-runtime/ | grep "kind: SandboxTemplate" | wc -l
```

Expected: `5`

```bash
helm template test-release deploy/sandbox-runtime/ | grep "kind: SandboxWarmPool" | wc -l
```

Expected: `1` (only tiny has warmPool enabled)

**Step 4: Verify template names rendered correctly**

```bash
helm template test-release deploy/sandbox-runtime/ | grep "name: aio-sandbox-"
```

Expected: 5 lines — `aio-sandbox-tiny`, `aio-sandbox-small`, `aio-sandbox-medium`, `aio-sandbox-large`, `aio-sandbox-xlarge`
