# Treadstone Deployment Guide

This document describes how to deploy Treadstone to Kubernetes and perform basic validation. It is intended for both human developers and AI Agents.

## Architecture Overview

The deployment consists of four layers of Helm charts, ordered by dependency from bottom to top:

| Layer | Chart | Description |
|-------|-------|-------------|
| Storage | `deploy/cluster-storage` | Cluster-scoped StorageClass aliases for persistent sandbox workspaces |
| Infra | `deploy/agent-sandbox` | Sandbox CRD + controller (cluster-scoped, deploy once) |
| Runtime | `deploy/sandbox-runtime` | SandboxTemplate + WarmPool (namespace-scoped) |
| App | `deploy/treadstone` | FastAPI application + Ingress + RBAC + Migration Job |

The app/runtime layers use the `ENV` variable (`local`, `demo`, `prod`). Cluster storage uses `CLUSTER_PROFILE`
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
#   TREADSTONE_JWT_SECRET     — JWT secret
#   TREADSTONE_LEADER_ELECTION_ENABLED=true  — Recommended for every K8s environment
```

## One-Command Deployment (Recommended)

### Local Environment

`make up` automatically handles: creating the Kind cluster → installing ingress-nginx → building the image → loading the image into the cluster → deploying all Helm charts.

```bash
make up              # Equivalent to make up ENV=local
```

### Demo / Prod Environments

```bash
make up ENV=demo CLUSTER_PROFILE=ack     # Requires an existing, accessible K8s cluster
make up ENV=prod CLUSTER_PROFILE=ack
```

### One-Command Teardown

```bash
make down            # Also deletes the Kind cluster in local environment
make down ENV=demo
```

## Step-by-Step Deployment

For more granular control, you can deploy layer by layer.

### 1. Create Kind Cluster (local only)

```bash
make kind-create
```

The cluster configuration is located at `deploy/kind/kind-config.yaml`: 1 control-plane + 2 workers, with automatic port mapping for 80/443 and ingress-nginx installed.

### 2. Build and Load Image (local only)

```bash
make build
kind load docker-image treadstone:latest --name treadstone
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
make deploy-app ENV=local       # App + Secret + Migration
```

`deploy-app` automatically creates a K8s Secret (`treadstone-secrets`) from `.env.local`, and runs the database migration in a Helm pre-install/pre-upgrade hook.
Persistent sandboxes use `TREADSTONE_SANDBOX_STORAGE_CLASS` from the environment file and default to a 5 GiB workspace.

### 4. Verify Deployment

```bash
# Replace <ENV> with local/demo/prod; namespace = treadstone-<ENV>
kubectl get pods -n treadstone-local
kubectl -n treadstone-local rollout status deploy/treadstone-local-treadstone --timeout=60s
```

## Accessing the Service

### Via Ingress (enabled by default in local)

The Kind cluster maps ports 80/443, access directly at `http://localhost`:

```bash
curl http://localhost/health
```

### Via port-forward (alternative)

```bash
make port-forward
# Access http://localhost:8000 in another terminal
curl http://localhost:8000/health
```

## Basic Validation (Smoke Test)

**Automated**: Run `make test-e2e` to execute the full E2E test suite against the deployed service. Override the target with `make test-e2e BASE_URL=http://localhost:8000` when using port-forward.

**Manual**: The following commands can quickly verify that the deployment is working. Use `BASE_URL=http://localhost` with Ingress, or `BASE_URL=http://localhost:8000` with port-forward.

```bash
BASE_URL=http://localhost
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
make build
kind load docker-image treadstone:latest --name treadstone
make restart-app

# Or run make up to redo the full flow
```

### Uninstall

```bash
make undeploy-app                  # Uninstall app only
make undeploy-all                  # Uninstall app + runtime (keep shared infra + storage)
make down                          # Tear down everything (including Kind cluster in local)
```

### Delete Kind Cluster

```bash
make kind-delete
```

## Environment Differences

| Config | local | demo | prod |
|--------|-------|------|------|
| K8s Namespace | `treadstone-local` | `treadstone-demo` | `treadstone-prod` |
| Helm release (app) | `treadstone-local` | `treadstone-demo` | `treadstone-prod` |
| Helm release (runtime) | `sandbox-runtime-local` | `sandbox-runtime-demo` | `sandbox-runtime-prod` |
| Image source | Local build | `ghcr.io/earayu/treadstone` | Specified by CI/CD |
| Replicas | 1 | 1 | 2 |
| HPA | Off | Off | On (2–10) |
| Ingress | `localhost` | `demo.treadstone-ai.dev` | `api.treadstone-ai.dev` + TLS |
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
| `curl localhost` connection refused | ingress-nginx not ready or port conflict | Rebuild cluster with `make kind-delete && make kind-create`, or use `make port-forward` |
| 403 Forbidden in pod logs | Insufficient RBAC permissions | Confirm the Helm chart deployed ClusterRole + ClusterRoleBinding |
| Sandbox Pod in CrashLoopBackOff | Kind cannot pull sandbox image | `docker pull <image> && kind load docker-image <image> --name treadstone` |

## Makefile Command Reference

```bash
make help              # List all available commands
make kind-create       # Create Kind cluster
make kind-delete       # Delete Kind cluster
make build             # Build Docker image
make deploy-all        # Deploy all layers (infra + runtime + app)
make deploy-app        # Deploy app only
make restart-app       # Rolling restart
make port-forward      # Forward port to localhost:8000
make undeploy-all      # Uninstall app + runtime
make test-e2e          # Run E2E tests against deployed service
make up                # One-command deploy (includes cluster creation for local)
make down              # One-command teardown
```
