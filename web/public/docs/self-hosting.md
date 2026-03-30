# Self-Hosting

## What this page is for

Describe the deployment model before you run commands.

## Use this when

- You want to deploy Treadstone on Kubernetes.
- You need to understand the Helm layers and prerequisites.
- You want the right entrypoint into local or production ops docs.

## Shortest path

```bash
cp .env.example .env.local
make up
make test-e2e
```

## Hard rules

- Treadstone is a Kubernetes deployment, not a single binary drop.
- The deployment has five layers. Respect the dependency order.
- Use `.env.<ENV>` files for Kubernetes environments.

## Architecture

The stack is deployed in five layers:

1. `deploy/cluster-storage`
2. `deploy/agent-sandbox`
3. `deploy/sandbox-runtime`
4. `deploy/treadstone`
5. `deploy/treadstone-web`

## Prerequisites

- Kubernetes access
- Helm
- kubectl
- Docker for local image builds
- Neon-compatible PostgreSQL connection string
- a real `TREADSTONE_JWT_SECRET`

## Environment Files

Prepare `.env.<ENV>` and set at minimum:

- `TREADSTONE_DATABASE_URL`
- `TREADSTONE_JWT_SECRET`
- `TREADSTONE_LEADER_ELECTION_ENABLED=true`

Optional auth providers:

- Google OAuth client ID and secret
- GitHub OAuth client ID and secret

## Next Reads

- Local cluster and repo workflow: [`local-development.md`](/docs/local-development.md)
- Public deployment concerns: [`production-deployment.md`](/docs/production-deployment.md)
- Common failure modes: [`troubleshooting.md`](/docs/troubleshooting.md)

## For Agents

- Do not skip directly to random `kubectl` commands when `make up` already covers the local path.
- When a production problem looks like routing or auth, read the production page before patching manifests blindly.
