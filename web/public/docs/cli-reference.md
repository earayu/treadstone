# CLI Reference

## What this page is for

Document the real command tree that exists today.

## Use this when

- You need exact command names, not approximations.
- You need auth precedence or config precedence.
- You need to know where `skills` lives.

## Shortest path

```bash
treadstone --help
treadstone system health
treadstone auth login
treadstone --json sandboxes create --name demo
treadstone skills
treadstone skills install
```

## Hard rules

- There is no top-level `health` command. Use `treadstone system health`.
- There is no `guide` command. The built-in agent guide lives under `skills`.
- Protected commands prefer API key over saved session.
- CLI config priority is flag, then env var, then config file.

## Root Options

- `--json`
- `--api-key`
- `--base-url`

## Root Command Groups

- `system`
- `auth`
- `api-keys`
- `sandboxes`
- `templates`
- `config`
- `skills`

## Auth Precedence

Protected commands use:

1. `--api-key`
2. `TREADSTONE_API_KEY`
3. saved config `api_key`
4. saved login session

If both API key and session exist, API key wins.

## Command Reference

### `system`

- `treadstone system health`

### `auth`

- `treadstone auth register`
- `treadstone auth login`
- `treadstone auth logout`
- `treadstone auth whoami`
- `treadstone auth resend-verification`
- `treadstone auth change-password`
- `treadstone auth users`
- `treadstone auth delete-user`

### `api-keys`

- `treadstone api-keys create`
- `treadstone api-keys list`
- `treadstone api-keys update`
- `treadstone api-keys delete`

### `sandboxes`

- `treadstone sandboxes create`
- `treadstone sandboxes list`
- `treadstone sandboxes get`
- `treadstone sandboxes start`
- `treadstone sandboxes stop`
- `treadstone sandboxes delete`

Browser hand-off subgroup:

- `treadstone sandboxes web enable`
- `treadstone sandboxes web status`
- `treadstone sandboxes web disable`

### `templates`

- `treadstone templates list`

### `config`

- `treadstone config set`
- `treadstone config get`
- `treadstone config unset`
- `treadstone config path`

### `skills`

- `treadstone skills`
- `treadstone skills install`

## JSON Mode

Use `--json` when you need:

- `sandbox_id`
- `urls.proxy`
- `urls.web`
- `web_url`
- `open_link`
- structured API-key scope details

## Configuration Keys

- `base_url`
- `api_key`
- `default_template`

## For Agents

- Treat CLI help and `--json` output as the source of truth for the CLI surface.
- When a workflow needs stable fields, prefer `--json` even if a human would accept table output.
