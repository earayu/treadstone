# CLI Reference

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

Protected commands use credentials in this order:

1. `--api-key`
2. `TREADSTONE_API_KEY`
3. saved config `api_key`
4. saved login session

If both an API key and a session exist, the API key wins.

## Core Commands

### System

- `treadstone system health`

### Auth

- `treadstone auth register`
- `treadstone auth login`
- `treadstone auth logout`
- `treadstone auth whoami`
- `treadstone auth resend-verification`
- `treadstone auth change-password`
- `treadstone auth users`
- `treadstone auth delete-user`

### API keys

- `treadstone api-keys create`
- `treadstone api-keys list`
- `treadstone api-keys update`
- `treadstone api-keys delete`

### Sandboxes

- `treadstone sandboxes create`
- `treadstone sandboxes list`
- `treadstone sandboxes get`
- `treadstone sandboxes start`
- `treadstone sandboxes stop`
- `treadstone sandboxes delete`

Browser handoff subgroup:

- `treadstone sandboxes web enable`
- `treadstone sandboxes web status`
- `treadstone sandboxes web disable`

### Templates

- `treadstone templates list`

### Config

- `treadstone config set`
- `treadstone config get`
- `treadstone config unset`
- `treadstone config path`

### Skills

- `treadstone skills`
- `treadstone skills install`

## Configuration Keys

- `base_url`
- `api_key`
- `default_template`

## CLI Facts

- `treadstone sandboxes` without a subcommand is the same as `treadstone sandboxes list`.
- `treadstone system health` is the connectivity check. There is no top-level `health` command.
- `--json` is the stable mode for parsing `id`, `urls.proxy`, `urls.web`, `web_url`, and `open_link`.
- `skills` is a real command group. There is no `guide` command.

> For automation: prefer `--json` whenever another tool, agent, or script will consume the result.
