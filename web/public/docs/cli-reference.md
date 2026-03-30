# CLI Reference

The Treadstone CLI (`treadstone`) is the primary interface for humans and AI agents to interact with the sandbox platform.

## Installation

**macOS / Linux:**

```bash
curl -fsSL https://github.com/earayu/treadstone/releases/latest/download/install.sh | sh
```

**Windows PowerShell:**

```powershell
irm https://github.com/earayu/treadstone/releases/latest/download/install.ps1 | iex
```

**Alternative (pip):**

```bash
pip install treadstone-cli
```

## Configuration

The CLI reads configuration from three sources, in order of priority:

| Priority | Source | Example |
|----------|--------|---------|
| 1 (highest) | CLI flags | `--base-url https://... --api-key ts_...` |
| 2 | Environment variables | `TREADSTONE_BASE_URL`, `TREADSTONE_API_KEY` |
| 3 (lowest) | Config file | `~/.config/treadstone/config.toml` |

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TREADSTONE_BASE_URL` | Base URL of the Treadstone server | `https://api.treadstone-ai.dev` |
| `TREADSTONE_API_KEY` | API key for authentication | (none) |
| `TREADSTONE_DEFAULT_TEMPLATE` | Default template for `sandboxes create` | `aio-sandbox-tiny` |

### Config File

Location: `~/.config/treadstone/config.toml`

```toml
[default]
base_url         = "https://your-server.example.com"
api_key          = "ts_live_xxxxxxxxxxxx"
default_template = "aio-sandbox-medium"
```

```bash
treadstone config set base_url https://your-server.example.com
treadstone config set api_key ts_live_xxxxxxxxxxxx
treadstone config set default_template aio-sandbox-medium
treadstone config get
treadstone config unset api_key
treadstone config path
```

## Global Flags

| Flag | Description |
|------|-------------|
| `--base-url URL` | Override the server URL |
| `--api-key KEY` | Override the API key |
| `--json` | Output responses as JSON |
| `--skills` | Print the built-in agent skill |
| `--version` | Show CLI version |
| `--help` | Show help message |

## Commands

### `system`

Inspect server reachability.

```bash
treadstone system
treadstone system health
```

### `auth`

Authentication and user management.

```bash
treadstone auth register                 # Create a new account
treadstone auth login                    # Log in and save a local session
treadstone auth logout                   # Clear the saved session
treadstone auth whoami                   # Show the current user
treadstone auth change-password          # Change your password
treadstone auth users                    # List users (admins see all)
treadstone auth delete-user <user-id>    # Delete a user (admin only)
```

### `sandboxes` (alias: `sb`)

Create and manage sandboxes. Sandbox names must be 1–55 characters of lowercase letters, numbers, or hyphens, starting and ending with a letter or number.

```bash
treadstone sandboxes                                         # list (shortcut)
treadstone sandboxes create --name my-box
treadstone sandboxes create --template aio-sandbox-medium --label env:dev --persist
treadstone sandboxes create --template aio-sandbox-large --persist --storage-size 5Gi
treadstone sandboxes list --label env:prod --limit 10
treadstone sandboxes get <sandbox-id>
treadstone sandboxes start <sandbox-id>
treadstone sandboxes stop <sandbox-id>
treadstone sandboxes delete <sandbox-id>
treadstone sandboxes web enable <sandbox-id>
treadstone sandboxes web status <sandbox-id>
treadstone sandboxes web disable <sandbox-id>
```

Persistent storage tiers: `5Gi`, `10Gi`, `20Gi`.

### `templates`

List available sandbox templates.

```bash
treadstone templates
treadstone templates list
```

### `api-keys`

Manage long-lived API keys.

```bash
treadstone api-keys create --name ci-bot
treadstone api-keys create --name ci-bot --save
treadstone api-keys create --name temp --expires-in 86400  # 24h TTL
treadstone api-keys create --no-control-plane --data-plane selected --sandbox-id sb123
treadstone api-keys list
treadstone api-keys update <key-id> --data-plane none
treadstone api-keys delete <key-id>
```

### `guide`

Print built-in guides.

```bash
treadstone guide agent       # Print agent skill guide
treadstone --skills          # Print agent skill in SKILL.md format
```

## JSON Output

Pass `--json` before any command for machine-readable output:

```bash
treadstone --json sandboxes list
treadstone --json system
treadstone --json sandboxes web enable <sandbox-id>
treadstone --json api-keys list
```

`sandboxes web enable` is idempotent — it returns the current active hand-off URL if one already exists. To rotate the URL, disable web access first then re-enable it.

## AI Agent Tips

- Always use `sandbox_id` (not `name`) for follow-up commands
- Read browser URLs from `urls.web` / `web_url` in JSON output — do not construct them from the name
- Use `treadstone guide agent` to get an embedded skill document optimized for LLM context
- Use `treadstone --skills` to get a SKILL.md-formatted version compatible with Cursor, Codex, and similar tools
