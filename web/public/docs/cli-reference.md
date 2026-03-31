# CLI Reference

## Root Options

| Option | Description |
|--------|-------------|
| `--json` | Output structured JSON instead of formatted tables. Safe for downstream parsing by scripts and agents. |
| `--api-key` | Use this API key for the command instead of the saved session or environment variable. |
| `--base-url` | Override the target API URL. Defaults to `TREADSTONE_BASE_URL` or the saved config value. |

## Auth Precedence

When a command requires credentials, the CLI checks in this order:

1. `--api-key` flag
2. `TREADSTONE_API_KEY` environment variable
3. Saved config `api_key`
4. Saved login session

If both an API key and a session exist, the API key wins.

## Commands

### `system`

| Command | What it does |
|---------|--------------|
| `treadstone system health` | Check connectivity to the hosted API. This is the only connectivity check; there is no top-level `health` command. |

### `auth`

| Command | What it does |
|---------|--------------|
| `treadstone auth register` | Create a new account interactively. |
| `treadstone auth login` | Sign in and save a session locally. Pass `--email` and `--password` for non-interactive use. |
| `treadstone auth logout` | Invalidate and clear the saved session. |
| `treadstone auth whoami` | Print the currently authenticated user and email verification status. |
| `treadstone auth resend-verification` | Request another email verification link for the current account. |
| `treadstone auth change-password` | Change the password for the current account. |
| `treadstone auth users` | List all user accounts. Admin only. |
| `treadstone auth delete-user` | Delete a user account by ID. Admin only. |

### `api-keys`

| Command | What it does |
|---------|--------------|
| `treadstone api-keys create` | Create a new API key. Key flags: `--name` (required), `--save` (write to local config), `--no-control-plane`, `--data-plane [none\|all\|selected]`, `--sandbox-id`. The full key value is shown once only. |
| `treadstone api-keys list` | List all API keys for the current account with their scope and enabled status. |
| `treadstone api-keys update` | Rename, enable, disable, or change the scope of an existing key by ID. |
| `treadstone api-keys delete` | Permanently delete an API key by ID. |

### `sandboxes`

| Command | What it does |
|---------|--------------|
| `treadstone sandboxes create` | Create a new sandbox. Key flags: `--template` (required), `--name`, `--label`, `--auto-stop-interval`, `--auto-delete-interval`, `--persist`, `--storage-size`. |
| `treadstone sandboxes list` | List sandboxes for the current account. Aliased from `treadstone sandboxes` with no subcommand. |
| `treadstone sandboxes get` | Get the full detail record for one sandbox by ID. |
| `treadstone sandboxes start` | Start a stopped sandbox by ID. |
| `treadstone sandboxes stop` | Stop a running sandbox by ID without deleting it. |
| `treadstone sandboxes delete` | Delete a sandbox and release its resources. |

Browser handoff subgroup:

| Command | What it does |
|---------|--------------|
| `treadstone sandboxes web enable` | Create or refresh a browser handoff session. Returns `open_link`, `web_url`, and `expires_at`. If a session is already active, returns the current live link. |
| `treadstone sandboxes web status` | Get the current handoff state: `enabled`, `web_url`, `expires_at`, `last_used_at`. Does not return `open_link`. |
| `treadstone sandboxes web disable` | Revoke the current handoff link immediately. |

### `templates`

| Command | What it does |
|---------|--------------|
| `treadstone templates list` | List the sandbox templates available to the current account. Use these names for `sandboxes create --template`. |

### `config`

| Command | What it does |
|---------|--------------|
| `treadstone config set` | Set a config key-value pair in the local config file. |
| `treadstone config get` | Read a config value by key. |
| `treadstone config unset` | Remove a config key. |
| `treadstone config path` | Print the path to the config file on disk. |

### `skills`

| Command | What it does |
|---------|--------------|
| `treadstone skills` | List installed CLI skills. Skills are optional; core hosted usage does not depend on them. |
| `treadstone skills install` | Install a CLI skill by name or URL. |

## Configuration Keys

| Key | Description |
|-----|-------------|
| `base_url` | The API base URL. Can also be set via `TREADSTONE_BASE_URL`. |
| `api_key` | A saved API key used as a fallback when `--api-key` and `TREADSTONE_API_KEY` are not present. |
| `default_template` | A default template name used by `sandboxes create` when `--template` is not specified. |

> For automation: prefer `--json` whenever another tool, agent, or script will consume the result. Parse `id`, `urls.proxy`, `urls.web`, `web_url`, and `open_link` from that output. Only `open_link` is shareable as a bearer URL; `web_url` requires a Console login.
