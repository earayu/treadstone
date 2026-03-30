# Production Deployment

## What this page is for

Call out the settings and behaviors that matter once the platform is public.

## Use this when

- You are preparing demo or prod.
- You need to set public origins correctly.
- You need to understand the difference between local and real deployments.

## Shortest path

1. Prepare `.env.prod`.
2. Set a real `TREADSTONE_APP_BASE_URL`.
3. Enable leader election.
4. Configure OAuth callbacks and public ingress hosts.
5. Deploy with `make up ENV=prod CLUSTER_PROFILE=...`.

## Hard rules

- Do not leave the default JWT secret in place.
- If `TREADSTONE_SANDBOX_DOMAIN` is public, `TREADSTONE_APP_BASE_URL` must also be public.
- Enable leader election for multi-replica deployments.
- Turn metering enforcement on before production.

## Required Production Settings

- `TREADSTONE_DATABASE_URL`
- `TREADSTONE_JWT_SECRET`
- `TREADSTONE_APP_BASE_URL`
- `TREADSTONE_LEADER_ELECTION_ENABLED=true`
- `TREADSTONE_METERING_ENFORCEMENT_ENABLED=true`

When browser subdomains are enabled:

- `TREADSTONE_SANDBOX_DOMAIN`
- `TREADSTONE_SANDBOX_SUBDOMAIN_PREFIX`

## OAuth Callbacks

Register provider callbacks that match the public environment:

- `https://<public-app-origin>/v1/auth/google/callback`
- `https://<public-app-origin>/v1/auth/github/callback`

## Deployment Shape

- local usually runs one replica
- production may run multiple API replicas
- leader election prevents duplicated singleton background work

## Validate After Deploy

- `GET /health`
- auth register and login
- template list
- sandbox create
- browser hand-off
- `make test-e2e` against the deployed cluster

## For Agents

- If browser hand-off fails only in prod, inspect public origin and sandbox-domain settings first.
- If quota behavior differs between local and prod, inspect metering-enforcement settings next.
