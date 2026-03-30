# Local Development

## What this page is for

Give developers and agents the repo-native local workflow.

## Use this when

- You are running the stack locally.
- You need the right `make` targets.
- You want to verify the deployment with repo-native checks.

## Shortest path

```bash
make install
make dev-api
make dev-web
```

For the full Kubernetes path:

```bash
cp .env.example .env.local
make up
make test-e2e
```

## Hard rules

- `make test-e2e` is the preferred smoke test after `make up`.
- `make dev-api` and `make dev-web` are the lightweight app-dev path.
- Local Kubernetes uses Kind.

## Common Commands

- `make install`
- `make dev-api`
- `make dev-web`
- `make test`
- `make lint`
- `make up`
- `make down`
- `make test-e2e`

## Database and Migrations

- local app-dev reads `.env`
- Kubernetes deploys read `.env.<ENV>`
- apply migrations with `make migrate`

## Client Generation

- `make gen-openapi`
- `make gen-web-types`
- `make gen-sdk-python`
- `make gen-public-docs`

## Fast Verification

```bash
curl http://localhost:8000/health
```

If local ingress is up:

```bash
curl http://localhost/health
```

## For Agents

- Prefer repo `make` targets over ad hoc sequences.
- If the change is docs-only, at least run `git diff --check` and the targeted docs tests.
