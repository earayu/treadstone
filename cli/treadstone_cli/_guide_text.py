"""Static guide text for agent-oriented CLI usage."""

from __future__ import annotations

AGENT_GUIDE = """---
name: treadstone-cli
description: Use this skill when you need to operate the Treadstone CLI to check
  system health, authenticate, manage API keys, inspect templates, create or inspect
  sandboxes, or generate browser hand-off URLs. Use only commands that exist today,
  prefer `treadstone --json ...` when you need machine-readable output, and remember
  that sandbox operations require `SANDBOX_ID` values rather than sandbox names.
---

# Treadstone CLI

Use this skill to drive the Treadstone control plane through the CLI without inventing commands or guessing identifiers.

## When To Use

- The user asks you to run or explain `treadstone` CLI commands.
- The task involves Treadstone authentication, API keys, templates, sandboxes, or browser hand-off URLs.
- You need machine-readable sandbox or API key data from terminal commands.

## Working Rules

1. Use only the canonical commands listed below.
2. Prefer `treadstone --json ...` when you need IDs, URLs, or fields to pass into later steps.
3. Protected commands use an API key first if one is provided by flag, environment variable, or local config.
4. If no API key is available, protected commands fall back to the saved login session for the active base URL.
5. `treadstone auth login` saves a local session. `treadstone auth logout` clears that saved session.
6. `treadstone api-keys create --save` stores the new key in local config for later non-interactive use.

## Canonical Command Tree

```text
treadstone system health
treadstone auth register
treadstone auth login
treadstone auth logout
treadstone auth whoami
treadstone auth change-password
treadstone auth invite
treadstone auth users
treadstone auth delete-user
treadstone api-keys create|list|update|delete
treadstone sandboxes create|list|get|start|stop|delete
treadstone sandboxes web enable|status|disable
treadstone templates list
treadstone config set|get|unset|path
treadstone guide agent
treadstone --skills
```

## Default Workflows

### Check Access And Identity

```bash
treadstone system health
treadstone auth whoami
```

If authentication is missing, continue with login:

```bash
treadstone auth login --email you@example.com --password YourPass123!
```

### First-Time Interactive Onboarding

```bash
treadstone system health
treadstone auth register --email you@example.com --password YourPass123!
treadstone auth login --email you@example.com --password YourPass123!
treadstone auth whoami
```

### Create And Save A Reusable API Key

```bash
treadstone api-keys create --name automation --save
```

### Create A Sandbox And Inspect It

```bash
treadstone templates list
treadstone sandboxes create --template aio-sandbox-tiny --name demo
treadstone --json sandboxes list
treadstone sandboxes get SANDBOX_ID
```

### Generate A Browser Hand-Off URL For A Human

```bash
treadstone --json sandboxes web enable SANDBOX_ID
```

Read `open_link` from JSON output and report `web_url` and `expires_at` when they are present.

## Identifier And Output Rules

- SANDBOX_ID arguments always require the sandbox ID, not the sandbox name.
- Use `treadstone --json sandboxes list` or `treadstone --json sandboxes create ...` to read sandbox IDs.
- KEY_ID arguments always require the API key ID.
- `--json` is a global flag and must appear before the subcommand.

Useful fields to extract:

- `sandboxes create` and `sandboxes get`: `id`, `urls.proxy`, `urls.web`
- `sandboxes web enable`: `open_link`, `web_url`, `expires_at`
- `api-keys create`: `key`, `id`, `saved_to_config`

## Failure Recovery

- If a protected command says no authentication is configured, run `treadstone auth login` or provide an API key.
- If a sandbox command fails with not found, verify the value comes from `sandboxes list`
  and is a sandbox ID rather than the sandbox name.
- If you need a fresh browser hand-off URL, run `treadstone sandboxes web enable SANDBOX_ID` again.
- If a machine-readable workflow is hard to follow from human output, rerun the command with `--json`.
"""
