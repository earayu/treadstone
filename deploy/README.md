# Treadstone Deployment Guide

This document describes how to deploy Treadstone to Kubernetes and perform basic validation. It is intended for both human developers and AI Agents.

## Architecture Overview

The deployment consists of five layers of Helm charts, ordered by dependency from bottom to top:

| Layer | Chart | Description |
|-------|-------|-------------|
| Storage | `deploy/cluster-storage` | Cluster-scoped StorageClass aliases for persistent sandbox workspaces |
| Infra | `deploy/agent-sandbox` | Sandbox CRD + controller (cluster-scoped, deploy once) |
| Runtime | `deploy/sandbox-runtime` | SandboxTemplate + WarmPool (namespace-scoped) |
| API | `deploy/treadstone` | FastAPI API service + Ingress + RBAC + Migration Job |
| Web | `deploy/treadstone-web` | React web frontend + Service + Ingress |

The API/web/runtime layers use the `ENV` variable (`local`, `demo`, `prod`). Cluster storage uses `CLUSTER_PROFILE`
(`local`, `ack`, `aws`) because `StorageClass` resources are cluster-scoped rather than namespace-scoped.

## Prerequisites

- Docker Desktop installed and running
- Kind installed (`brew install kind`)
- kubectl installed (`brew install kubectl`)
- Helm installed (`brew install helm`)
- Hurl installed (`brew install hurl`) — for E2E tests
- Neon database connection string ready

## Environment Configuration Files

Before deploying, prepare a `.env.{ENV}` file (e.g. `.env.local`). Refer to `.env.example` for the format:

```bash
cp .env.example .env.local
# Edit .env.local and fill in at minimum:
#   TREADSTONE_DATABASE_URL   — Neon connection string
#   TREADSTONE_JWT_SECRET     — at least 32 characters (see .env.example)
#   TREADSTONE_APP_BASE_URL     — http://app.localhost (Web UI origin; matches Helm for local)
#   TREADSTONE_LEADER_ELECTION_ENABLED=true  — Recommended for every K8s environment (default in .env.example)
# Optional for Google/GitHub login:
#   TREADSTONE_GOOGLE_OAUTH_CLIENT_ID / TREADSTONE_GOOGLE_OAUTH_CLIENT_SECRET
#   TREADSTONE_GITHUB_OAUTH_CLIENT_ID / TREADSTONE_GITHUB_OAUTH_CLIENT_SECRET
```

For OAuth provider setup, register callback URLs that match `TREADSTONE_APP_BASE_URL` (browser flows go through the Web app host, which proxies `/v1/` to the API):

- local (Kind + Ingress): `http://app.localhost/v1/auth/google/callback` and `http://app.localhost/v1/auth/github/callback`
- demo/prod: `https://app-demo.treadstone-ai.dev/...` / `https://app.treadstone-ai.dev/...` (see `.env.example` comments)

## kubectl context

Helm and `kubectl` use **whatever context is currently selected** in your kubeconfig.

Set **`TREADSTONE_PROD_CONTEXT`** to the **kubeconfig context name of your production cluster** (the string shown by `kubectl config get-contexts` for prod — not a generic “current context” placeholder).

| Command | Role of `TREADSTONE_PROD_CONTEXT` |
|---------|-------------------------------------|
| **`make prod`** | **Required.** Refused unless `kubectl config current-context` **equals** `TREADSTONE_PROD_CONTEXT`, so you only deploy to prod when explicitly pointed at prod. |
| **`make local`** / **`make destroy-local`** | **Optional.** If set, these commands are **refused** when the current context **equals** `TREADSTONE_PROD_CONTEXT` (avoids Kind / local teardown while kubectl still points at production). If unset, this guard is skipped — better for contributors who do not know your prod context name. |

[`scripts/check-k8s-context.sh`](../scripts/check-k8s-context.sh) implements the above; it does **not** change your context automatically.

For local Kind, switch to your Kind context manually (typically `kind-treadstone` when the cluster name is `treadstone`):

```bash
kubectl config use-context kind-treadstone
make local
```

### Production

```bash
export TREADSTONE_PROD_CONTEXT=<your-prod-context-name>
kubectl config use-context "$TREADSTONE_PROD_CONTEXT"
make prod    # runs deploy-all ENV=prod (default CLUSTER_PROFILE=ack)
```

### Demo or other remote environments

Use `deploy-all` (or individual `deploy-*` targets) with the right `ENV` and `CLUSTER_PROFILE` after switching `kubectl` to the intended cluster:

```bash
kubectl config use-context <your-demo-context>
make deploy-all ENV=demo CLUSTER_PROFILE=ack
```

### Local teardown

```bash
# Optional: export TREADSTONE_PROD_CONTEXT so destroy-local is refused while on prod
make destroy-local    # undeploy-env for local + delete Kind cluster
```

There is **no** `make` target to destroy prod or remote namespaces; use explicit `helm`/`kubectl` if you need that.

## Step-by-Step Deployment

For more granular control, you can deploy layer by layer.

### 1. Create Kind Cluster (local only)

```bash
make kind-create
```

The cluster configuration is located at `deploy/kind/kind-config.yaml`: 1 control-plane + 2 workers, with automatic port mapping for 80/443 and ingress-nginx installed.

### 2. Build and Load Images (local only)

```bash
make image-api
kind load docker-image treadstone:latest --name treadstone
make image-web
kind load docker-image treadstone-web:latest --name treadstone
```

### 3. Deploy All Helm Charts

```bash
make deploy-all ENV=local CLUSTER_PROFILE=local
```

This is equivalent to running in sequence:

```bash
make deploy-storage CLUSTER_PROFILE=local  # StorageClass aliases (cluster-scoped)
make deploy-infra ENV=local     # Sandbox CRD + controller
make deploy-runtime ENV=local   # SandboxTemplate + WarmPool
make deploy-api ENV=local       # API + Secret + Migration
make deploy-web ENV=local       # Web frontend
```

`deploy-api` automatically creates a K8s Secret (`treadstone-secrets`) from `.env.local`, and runs the database migration in a Helm pre-install/pre-upgrade hook.
Persistent sandboxes use `TREADSTONE_SANDBOX_STORAGE_CLASS` from the environment file and default to a 5 GiB workspace.

### Sandbox runtime image (local)

`deploy/sandbox-runtime/values-local.yaml` defaults to a **mainland China** mirror for the all-in-one sandbox image (see the `image:` field). This matches typical developer networks in China. If you are outside mainland China or the mirror is unreachable, switch the `image` value to `ghcr.io/agent-infra/sandbox:latest` (same as `values-prod.yaml`) and redeploy the runtime chart. You can also `docker pull` + `kind load docker-image` that tag before creating sandboxes.

### 4. Verify Deployment

```bash
# Replace <ENV> with local/demo/prod; namespace = treadstone-<ENV>
kubectl get pods -n treadstone-local
kubectl -n treadstone-local rollout status deploy/treadstone-local-treadstone --timeout=60s
```

## Accessing the Service

### Via Ingress (enabled by default in local)

The Kind cluster maps ports 80/443 to the host. Local uses two hostnames (aligned with production’s `api.*` / `app.*` split):

- **API (direct):** `http://api.localhost` — use for `curl`, CLI `TREADSTONE_BASE_URL`, SDK `base_url`, and `make test-e2e`.
- **Web UI:** `http://app.localhost` — React app; nginx proxies `/v1/` to the API service.

```bash
curl http://api.localhost/health
```

### Via port-forward (alternative)

```bash
make port-forward-api
# Access http://localhost:8000 in another terminal
curl http://localhost:8000/health
```

## Basic Validation (Smoke Test)

**Automated**: Run `make test-e2e` to execute the full E2E test suite against the deployed API (default `BASE_URL=http://api.localhost`). Override with `make test-e2e BASE_URL=http://localhost:8000` when using port-forward. Scenario list and data-plane prerequisites: [`tests/e2e/README.md`](../tests/e2e/README.md).

**Manual**: Use `BASE_URL=http://api.localhost` with Ingress, or `BASE_URL=http://localhost:8000` with port-forward.

```bash
BASE_URL=http://api.localhost
```

### Health Check

```bash
curl -s $BASE_URL/health
# Expected: {"status":"ok"}
```

### Register a User

The first registered user automatically becomes an admin:

```bash
curl -s -X POST $BASE_URL/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"StrongPass123!"}' | python3 -m json.tool
```

### Login & Create API Key

```bash
curl -s -c /tmp/cookies -X POST $BASE_URL/v1/auth/login \
  -d "username=admin@example.com&password=StrongPass123!"

curl -s -b /tmp/cookies -X POST $BASE_URL/v1/auth/api-keys \
  -H "Content-Type: application/json" \
  -d '{"name":"smoke-test"}' | python3 -m json.tool

# Note the returned key (sk-...)
export API_KEY="sk-your-key-here"
```

### Verify Sandbox Functionality

```bash
# List templates
curl -s $BASE_URL/v1/sandbox-templates \
  -H "Authorization: Bearer $API_KEY" | python3 -m json.tool

# Create a Sandbox
curl -s -X POST $BASE_URL/v1/sandboxes \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"template":"treadstone-sandbox","name":"smoke-test-sb"}' | python3 -m json.tool
```

After the Sandbox is running, you can reach its **Web UI** in a browser. The exact URL depends on your subdomain / DNS setup; with local Kind and Ingress, open `http://<sandbox-name>.sandbox.localhost/` (for example, `http://api-sb-1774074700.sandbox.localhost/`).

### Exposing the Sandbox MCP Endpoint Publicly

Each sandbox exposes its internal HTTP server (default port 8080) through two paths:

| Path | Auth | Use for |
|------|------|---------|
| `https://api.<domain>/v1/sandboxes/{id}/proxy/mcp` | API Key (`Authorization: Bearer sk-…`) | MCP clients (Cursor, Claude Desktop, scripts) — HTTP/SSE and WebSocket both supported |
| `https://sandbox-{id}.<sandbox_domain>/mcp` | Browser session cookie (with `/_treadstone/open` bootstrap) | Human-facing browser tools |

For WebSocket-based MCP clients that cannot set HTTP headers, pass the key as a query param: `wss://api.<domain>/v1/sandboxes/{id}/proxy/mcp?token=sk-…`.

### Using a Custom Domain for Sandbox Subdomains

By default, sandbox subdomains use `sandbox-{id}.treadstone-ai.dev`. To switch to your own domain (e.g. `mycompany.com`), set these environment variables in your secrets file and redeploy:

```bash
TREADSTONE_SANDBOX_DOMAIN=mycompany.com
TREADSTONE_APP_BASE_URL=https://app.mycompany.com
```

Then add the wildcard host to `deploy/treadstone/values-<env>.yaml`:

```yaml
ingress:
  hosts:
    - host: api.mycompany.com
      paths:
        - path: /
          pathType: Prefix
    - host: "*.mycompany.com"
      paths:
        - path: /
          pathType: Prefix
```

You will also need:
- A wildcard TLS certificate for `*.mycompany.com` (reference it via `ingress.tls` or the ALB `certificate-id` annotation).
- A DNS wildcard record `*.mycompany.com → <load balancer>` at your DNS provider.

> **Note:** `TREADSTONE_SANDBOX_DOMAIN` accepts a single domain. If you need both your custom domain and `treadstone-ai.dev` active simultaneously, add a CDN/reverse-proxy in front that rewrites the `Host` header to `sandbox-{id}.treadstone-ai.dev` for requests coming from your custom domain.

```bash
# View K8s resources (replace treadstone-local with your namespace)
kubectl -n treadstone-local get sandboxclaims,sandboxes,pods

# Clean up
curl -s -X DELETE $BASE_URL/v1/sandboxes/{sandbox_id} \
  -H "Authorization: Bearer $API_KEY"
```

## Day-to-Day Operations

### Redeploy (after code changes)

```bash
# local environment
make image-api
kind load docker-image treadstone:latest --name treadstone
make image-web
kind load docker-image treadstone-web:latest --name treadstone
make restart-api

# Or run make local to redo the full flow (use Kind context; see kubectl section above)
```

### Uninstall

```bash
make undeploy-api                  # Uninstall API only
make undeploy-env                  # Uninstall API + web + runtime (keep shared infra + storage)
make destroy-local                 # Tear down local env (including Kind cluster)
```

### Delete Kind Cluster

```bash
make kind-delete
```

## Environment Differences

| Config | local | demo | prod |
|--------|-------|------|------|
| K8s Namespace | `treadstone-local` | `treadstone-demo` | `treadstone-prod` |
| Helm release (api) | `treadstone-local` | `treadstone-demo` | `treadstone-prod` |
| Helm release (web) | `treadstone-web-local` | `treadstone-web-demo` | `treadstone-web-prod` |
| Helm release (runtime) | `sandbox-runtime-local` | `sandbox-runtime-demo` | `sandbox-runtime-prod` |
| Image source | Local build | `ghcr.io/earayu/treadstone` | Specified by CI/CD |
| Replicas | 1 | 1 | 2 |
| HPA | Off | Off | On (2–10) |
| Ingress | `api.localhost` (API) + `app.localhost` (Web) + `*.sandbox.localhost` | `demo.treadstone-ai.dev` | `api.treadstone-ai.dev` + TLS |
| ALB Group | — | `treadstone` (order 2) | `treadstone` (order 1) |
| DB migration | Auto (Helm hook) | Auto | Auto |

### Multi-Environment Isolation

Every environment runs in its own namespace (`treadstone-local` / `treadstone-demo` / `treadstone-prod`).
Each namespace has its own independent Deployment, Service, and K8s Secret — deploying one environment never touches another.

Both share a **single AWS ALB** via `alb.ingress.kubernetes.io/group.name: treadstone`.
The ALB controller merges their Ingress rules into one load balancer with host-based routing:

- `demo.treadstone-ai.dev` → Service in `treadstone-demo` namespace
- `api.treadstone-ai.dev` → Service in `treadstone-prod` namespace (order 1 = higher priority)

Before deploying prod, fill in `alb.ingress.kubernetes.io/certificate-arn` in `values-prod.yaml`
with the ACM certificate ARN for `api.treadstone-ai.dev`.

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| Templates API returns `python-dev` / `nodejs-dev` | `TREADSTONE_DEBUG=true` in `.env` | Set to `false` and recreate the Secret |
| API returns 500 + `column "xxx" does not exist` | Database is missing new columns | Migration Job should run automatically; manual fix: `kubectl -n treadstone-<ENV> exec deploy/treadstone-<ENV>-treadstone -- uv run alembic upgrade head` |
| Pod stuck not Ready | Image pull failure | For local: run `kind load docker-image` first; for remote: check image registry permissions |
| `curl http://api.localhost` connection refused | ingress-nginx not ready or port 80 conflict | Rebuild cluster with `make kind-delete && make kind-create`, or use `make port-forward-api` |
| 403 Forbidden in pod logs | Insufficient RBAC permissions | Confirm the Helm chart deployed ClusterRole + ClusterRoleBinding |
| Sandbox Pod in CrashLoopBackOff | Kind cannot pull sandbox image | `docker pull <image> && kind load docker-image <image> --name treadstone` |

## Makefile Command Reference

```bash
make help              # List all available commands
make kind-create       # Create Kind cluster
make kind-delete       # Delete Kind cluster
make image-api         # Build API Docker image
make image-web         # Build frontend Docker image
make deploy-all        # Deploy all layers (storage + infra + runtime + api + web)
make deploy-api        # Deploy API only
make deploy-web        # Deploy web only
make restart-api       # Rolling restart for the API
make port-forward-api  # Forward the API to localhost:8000
make undeploy-env      # Uninstall namespace-scoped layers
make test-e2e          # Run E2E tests against deployed service
make local             # Local Kind + images + deploy (optional TREADSTONE_PROD_CONTEXT guard)
make prod              # deploy-all ENV=prod (needs TREADSTONE_PROD_CONTEXT = current context)
make destroy-local     # Local teardown + Kind delete (optional TREADSTONE_PROD_CONTEXT guard)
```
