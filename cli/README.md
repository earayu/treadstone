# Treadstone CLI

Command-line interface for the Treadstone sandbox service.

## Installation

### Recommended: release installer

```bash
curl -fsSL https://github.com/earayu/treadstone/releases/latest/download/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://github.com/earayu/treadstone/releases/latest/download/install.ps1 | iex
```

The installer downloads the correct binary for your platform and verifies checksums when available.

### Alternative: PyPI

```bash
pip install treadstone-cli
```

## Quick start

### Human workflow

```bash
# Optional: point the CLI at your own deployment
export TREADSTONE_BASE_URL="http://localhost:8000"

# Check that the server is reachable
treadstone system health

# Register an account (first time only)
treadstone auth register

# Log in and save a local session for the active base URL
treadstone auth login

# Create an API key for non-interactive use and save it locally
treadstone api-keys create --name my-key --save

# Create a sandbox
treadstone sandboxes create --template aio-sandbox-tiny --name my-sandbox
# Name rules: 1-55 chars, lowercase letters/numbers/hyphens only,
# and must start/end with a letter or number. Names are only unique per user.

# List sandboxes
treadstone sandboxes list

# Create a browser hand-off URL for a human
treadstone sandboxes web enable <sandbox-id>

# Print the built-in agent skill
treadstone guide agent
treadstone --skills
```

### Agent workflow

For automation and AI agents, prefer JSON output and capture the returned sandbox ID from command output.

```bash
treadstone --json system health
treadstone auth register --email agent@example.com --password YourPass123!
treadstone auth login --email agent@example.com --password YourPass123!
treadstone --json api-keys create --name automation --save

treadstone --json templates list
treadstone --json sandboxes create --template aio-sandbox-tiny --name my-sandbox
treadstone --json sandboxes get <sandbox-id>
treadstone --json sandboxes web enable <sandbox-id>

treadstone guide agent
treadstone --skills
```

Treat `name` as a human-readable label only. Follow-up sandbox commands require
`SANDBOX_ID`, and browser URLs should come from `urls.web`, `web_url`, or
`open_link` rather than being constructed from the sandbox name.

## Configuration

The CLI reads configuration from three sources, in order of priority:

| Priority | Source | Example |
|----------|--------|---------|
| 1 (highest) | CLI flags | `--base-url https://... --api-key ts_...` |
| 2 | Environment variables | `TREADSTONE_BASE_URL`, `TREADSTONE_API_KEY` |
| 3 (lowest) | Config file | `~/.config/treadstone/config.toml` |

Saved login sessions are stored separately in `~/.config/treadstone/session.json`
and are only used when no API key is configured for the active base URL.

### Config file

Location: `~/.config/treadstone/config.toml`

```toml
[default]
base_url = "https://your-server.example.com"
api_key  = "ts_live_xxxxxxxxxxxx"
```

You can manage this file with the `config` subcommand:

```bash
# Set a value
treadstone config set base_url https://your-server.example.com
treadstone config set api_key ts_live_xxxxxxxxxxxx

# View current settings (api_key is partially masked)
treadstone config get

# View a single key
treadstone config get base_url

# Remove a value
treadstone config unset api_key

# Show config file path
treadstone config path
```

### Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TREADSTONE_BASE_URL` | Base URL of the Treadstone server | `https://api.treadstone-ai.dev` |
| `TREADSTONE_API_KEY` | API key for authentication | (none) |

### Global flags

| Flag | Description |
|------|-------------|
| `--base-url URL` | Override the server URL |
| `--api-key KEY` | Override the API key |
| `--json` | Output responses as JSON (useful for scripting) |
| `--skills` | Print the built-in agent skill in `SKILL.md` format for tools like GangGang, Codex, and Cursor |
| `--version` | Show CLI version |
| `--help` | Show help message |

## Commands

### `system`

Inspect server reachability and other platform-wide state.

```bash
treadstone system health
# Server is healthy
```

### `auth`

Authentication and user management.

```bash
treadstone auth register                 # Create a new account
treadstone auth login                    # Log in and save a local session
treadstone auth logout                   # Clear the saved session for this base URL
treadstone auth whoami                   # Show the current user via API key or session
treadstone auth change-password          # Change your password
treadstone auth invite --email user@example.com   # Invite a user (admin)
treadstone auth users                    # Admins see all users; non-admins see themselves
treadstone auth delete-user <user-id>    # Delete a user (admin)
```

### `sandboxes` (alias: `sb`)

Create and manage sandboxes.

Custom sandbox names must be 1-55 characters of lowercase letters, numbers, or hyphens. They must start and end
with a letter or number. Sandbox names only need to be unique for the current user.

```bash
treadstone sandboxes create --template aio-sandbox-tiny --name my-box
treadstone sandboxes create --template aio-sandbox-medium --label env:dev --persist
treadstone sandboxes list
treadstone sandboxes list --label env:prod --label team:agent --limit 10
treadstone sandboxes get <sandbox-id>
treadstone sandboxes start <sandbox-id>
treadstone sandboxes stop <sandbox-id>
treadstone sandboxes delete <sandbox-id>
treadstone sandboxes web enable <sandbox-id>
treadstone sandboxes web status <sandbox-id>
treadstone sandboxes web disable <sandbox-id>
```

### `templates`

List available sandbox templates.

```bash
treadstone templates list
```

### `api-keys`

Manage long-lived API keys.

```bash
treadstone api-keys create --name ci-bot
treadstone api-keys create --name ci-bot --save
treadstone api-keys create --name temp --expires-in 86400  # 24h
treadstone api-keys create --no-control-plane --data-plane selected --sandbox-id sb123
treadstone api-keys list
treadstone api-keys update <key-id> --data-plane none
treadstone api-keys delete <key-id>
```

### `config`

Manage local CLI configuration.

```bash
treadstone config set base_url https://...
treadstone config set api_key ts_...
treadstone config get
treadstone config get base_url
treadstone config unset api_key
treadstone config path
```

## JSON output

Pass `--json` before any command to get machine-readable JSON output:

```bash
treadstone --json sandboxes list
treadstone --json system health
treadstone --json sandboxes web enable <sandbox-id>
treadstone --json api-keys list
```

`treadstone sandboxes web enable <sandbox-id>` is idempotent: it returns the
current active browser hand-off URL when one already exists. If you need a new
hand-off URL, disable web access first and then enable it again.

## AI Agent usage

Use the CLI as a JSON-first interface when an agent needs to chain commands:

```bash
treadstone --json system health
treadstone --json templates list
treadstone --json sandboxes create --template aio-sandbox-tiny --name demo
treadstone --json sandboxes get <sandbox-id>
treadstone --json sandboxes web enable <sandbox-id>
```

Guidelines:

- Put `--json` before the subcommand.
- Pass `--email` and `--password` explicitly for non-interactive auth flows.
- Sandbox names are only unique for the current user. They are not accepted where `SANDBOX_ID` is required.
- Browser entry URLs are based on `sandbox_id` under the hood. Read `urls.web`, `web_url`, or `open_link` from command output instead of constructing URLs manually.
- `treadstone --skills` prints a built-in `SKILL.md` document that can be fed to agent runners.

## Error handling

The CLI displays user-friendly error messages instead of stack traces:

```
Error: Connection refused.
  Possible causes:
    - The Treadstone server is not running
    - The --base-url or TREADSTONE_BASE_URL is incorrect
    - A firewall or proxy is blocking the connection
  Detail: ...
```

Common errors:

| Error | Cause | Fix |
|-------|-------|-----|
| Connection refused | Server not running or wrong URL | Check `treadstone config get base_url` |
| Request timed out | Server slow or unreachable | Retry, or check network |
| No authentication configured | Missing API key and no saved session | `treadstone auth login` or `treadstone config set api_key <key>` |
| HTTP 401 | Invalid or expired API key | Create a new key with `treadstone api-keys create` |
| HTTP 404 | Resource not found | Verify the resource ID is correct; sandbox names are not accepted where `SANDBOX_ID` is required |
