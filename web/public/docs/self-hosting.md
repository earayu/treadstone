# Self-Hosting

Treadstone is fully open source and self-hostable on Kubernetes. This guide covers local development with Kind and production deployment.

## Prerequisites

- Docker Desktop (running)
- Kind: `brew install kind`
- kubectl: `brew install kubectl`
- Helm: `brew install helm`
- Hurl: `brew install hurl` (for E2E tests)
- A [Neon](https://neon.tech) database connection string

## Architecture

The deployment consists of five Helm chart layers:

| Layer | Chart | Description |
|-------|-------|-------------|
| Storage | `deploy/cluster-storage` | StorageClass aliases for persistent sandbox volumes |
| Infra | `deploy/agent-sandbox` | Sandbox CRD + controller (cluster-scoped, deploy once) |
| Runtime | `deploy/sandbox-runtime` | SandboxTemplate + WarmPool (namespace-scoped) |
| API | `deploy/treadstone` | FastAPI service + Ingress + RBAC + Migration Job |
| Web | `deploy/treadstone-web` | React frontend + Service + Ingress |

## Environment Configuration

Create a `.env.local` file from the example:

```bash
cp .env.example .env.local
```

Required fields:

```bash
TREADSTONE_DATABASE_URL=postgresql+asyncpg://user:pass@host/db?sslmode=require
TREADSTONE_JWT_SECRET=a-long-random-secret
TREADSTONE_LEADER_ELECTION_ENABLED=true
```

Optional (for OAuth):

```bash
TREADSTONE_GOOGLE_OAUTH_CLIENT_ID=...
TREADSTONE_GOOGLE_OAUTH_CLIENT_SECRET=...
TREADSTONE_GITHUB_OAUTH_CLIENT_ID=...
TREADSTONE_GITHUB_OAUTH_CLIENT_SECRET=...
```

Register OAuth callback URLs:

- Local: `http://localhost/v1/auth/google/callback`
- Production: `https://<api-host>/v1/auth/google/callback`

## Local Development (Kind)

### One-Command Setup

```bash
make up         # Creates Kind cluster, builds images, deploys all charts
```

This handles: create Kind cluster → install ingress-nginx → build API + web images → load into cluster → deploy Helm charts.

### Tear Down

```bash
make down
```

### Run E2E Tests

```bash
make test-e2e
```

## Step-by-Step Deployment

If you prefer manual control:

```bash
# 1. Create Kind cluster
kind create cluster --config deploy/kind-config.yaml

# 2. Install ingress-nginx
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/...

# 3. Deploy storage layer
helm install cluster-storage deploy/cluster-storage/

# 4. Deploy agent-sandbox CRD + controller
helm install agent-sandbox deploy/agent-sandbox/

# 5. Deploy sandbox runtime templates
helm install sandbox-runtime deploy/sandbox-runtime/

# 6. Deploy Treadstone API
helm install treadstone deploy/treadstone/ -f .env.local

# 7. Deploy web frontend
helm install treadstone-web deploy/treadstone-web/
```

## Production Deployment

For demo/prod environments:

```bash
make up ENV=prod
```

Ensure your `.env.prod` has production values including a strong `TREADSTONE_JWT_SECRET` and a production Neon connection string.

## Development Server (without Kubernetes)

For local API development without a full cluster:

```bash
# Install dependencies
make install

# Start API dev server (hot reload, port 8000)
make dev-api

# Start web dev server (hot reload, port 5173)
make dev-web
```

You still need a Neon database. Set `TREADSTONE_DATABASE_URL` in `.env`.

## Database Migrations

```bash
make migrate                # Apply pending migrations
make migration MSG="add column x"   # Generate a new migration
```

## Useful Make Commands

| Command | Purpose |
|---------|---------|
| `make install` | Install Python/web dependencies and git hooks |
| `make dev-api` | Start API dev server (localhost:8000, hot reload) |
| `make dev-web` | Start web dev server (localhost:5173, hot reload) |
| `make test` | Run tests (excludes integration) |
| `make test-all` | Run all tests including integration |
| `make test-e2e` | Run E2E tests against deployed cluster |
| `make lint` | Run Python + web lint checks |
| `make format-py` | Auto-format Python code |
| `make migrate` | Apply database migrations |
| `make migration MSG=x` | Generate a new Alembic migration |
| `make gen-openapi` | Export `openapi.json` from the FastAPI app |
| `make up` | Full K8s environment up |
| `make down` | Tear down local environment |

## License

[Apache License 2.0](https://github.com/earayu/treadstone/blob/main/LICENSE)
