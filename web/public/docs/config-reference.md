# Config Reference

## What this page is for

Collect the configuration knobs that most often affect public behavior.

## Use this when

- The CLI is pointing at the wrong server or key.
- OAuth or browser hand-off is behaving unexpectedly.
- You are configuring a deployment and need the key environment variables.

## Shortest path

```bash
treadstone config get
treadstone config path
```

## Hard rules

- CLI precedence is flag, then env var, then config file.
- `TREADSTONE_API_KEY` and a saved session are not equivalent.
- If `sandbox_domain` is enabled outside localhost, `app_base_url` must be a real public origin.

## CLI Config Keys

- `base_url`
- `api_key`
- `default_template`

Useful commands:

```bash
treadstone config set base_url https://api.treadstone-ai.dev
treadstone config set default_template aio-sandbox-small
treadstone config unset api_key
treadstone config path
```

## Core Environment Variables

- `TREADSTONE_DATABASE_URL`
- `TREADSTONE_JWT_SECRET`
- `TREADSTONE_APP_BASE_URL`
- `TREADSTONE_AUTH_TYPE`
- `TREADSTONE_EMAIL_BACKEND`
- `TREADSTONE_SANDBOX_NAMESPACE`
- `TREADSTONE_SANDBOX_PORT`
- `TREADSTONE_SANDBOX_STORAGE_CLASS`
- `TREADSTONE_SANDBOX_DEFAULT_STORAGE_SIZE`
- `TREADSTONE_METERING_ENFORCEMENT_ENABLED`
- `TREADSTONE_LEADER_ELECTION_ENABLED`
- `TREADSTONE_SANDBOX_DOMAIN`
- `TREADSTONE_SANDBOX_SUBDOMAIN_PREFIX`

## Auth Configuration

Built-in auth can expose these login methods depending on configuration:

- `email`
- `google`
- `github`

Public config is returned from:

```text
GET /v1/config
```

## Browser-Handoff Configuration

Browser hand-off needs:

- `TREADSTONE_SANDBOX_DOMAIN`
- `TREADSTONE_SANDBOX_SUBDOMAIN_PREFIX`
- `TREADSTONE_APP_BASE_URL`

Without a configured sandbox domain, canonical sandbox browser URLs are disabled.

## For Agents

- If CLI behavior looks wrong, inspect flag, env, and config precedence before assuming the server is wrong.
- If browser hand-off is missing `urls.web`, inspect sandbox-domain configuration next.
