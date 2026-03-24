# Treadstone CLI

Command-line interface for the Treadstone sandbox service.

## Installation

### From PyPI

```bash
pip install treadstone-cli
```

### Pre-built binary

Download the latest release from [GitHub Releases](https://github.com/earayu/treadstone/releases). The binary is self-contained and does not require Python.

```bash
# macOS / Linux
chmod +x treadstone
sudo mv treadstone /usr/local/bin/
```

## Quick start

```bash
# Check that the server is reachable
treadstone health

# Register an account (first time only)
treadstone auth register

# Log in
treadstone auth login

# Create an API key for non-interactive use
treadstone api-keys create --name my-key
# Save the key — it is shown only once

# Store the key in config so you don't have to pass it every time
treadstone config set api_key ts_live_xxxxxxxxxxxx

# Create a sandbox
treadstone sandboxes create --template default --name my-sandbox
# Name rules: 1-55 chars, lowercase letters/numbers/hyphens only,
# and must start/end with a letter or number.

# List sandboxes
treadstone sb list
```

## Configuration

The CLI reads configuration from three sources, in order of priority:

| Priority | Source | Example |
|----------|--------|---------|
| 1 (highest) | CLI flags | `--base-url https://... --api-key ts_...` |
| 2 | Environment variables | `TREADSTONE_BASE_URL`, `TREADSTONE_API_KEY` |
| 3 (lowest) | Config file | `~/.config/treadstone/config.toml` |

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
| `--version` | Show CLI version |
| `--help` | Show help message |

## Commands

### `health`

Check if the server is reachable and healthy.

```bash
treadstone health
# Server is healthy
```

### `auth`

Authentication and user management.

```bash
treadstone auth register                 # Create a new account
treadstone auth login                    # Log in interactively
treadstone auth logout                   # Log out
treadstone auth whoami                   # Show current user info
treadstone auth change-password          # Change your password
treadstone auth invite --email user@example.com   # Invite a user (admin)
treadstone auth users                    # List all users (admin)
treadstone auth delete-user <user-id>    # Delete a user (admin)
```

### `sandboxes` (alias: `sb`)

Create and manage sandboxes.

Custom sandbox names must be 1-55 characters of lowercase letters, numbers, or hyphens. They must start and end
with a letter or number. This keeps browser URLs like `sandbox-{name}.treadstone-ai.dev` within DNS label limits.

```bash
treadstone sb create --template default --name my-box
treadstone sb create --template python --label env:dev --persist
treadstone sb list
treadstone sb list --label env:prod --limit 10
treadstone sb get <sandbox-id>
treadstone sb start <sandbox-id>
treadstone sb stop <sandbox-id>
treadstone sb delete <sandbox-id>
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
treadstone --json sb list
treadstone --json health
treadstone --json api-keys list
```

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
| No API key configured | Missing authentication | `treadstone config set api_key <key>` |
| HTTP 401 | Invalid or expired API key | Create a new key with `treadstone api-keys create` |
| HTTP 404 | Resource not found | Verify the ID is correct |
