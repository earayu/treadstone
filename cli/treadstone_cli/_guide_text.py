"""Static guide text for agent-oriented CLI usage."""

from __future__ import annotations

AGENT_GUIDE = """---
name: treadstone-cli
description: Use this skill when you need to operate the Treadstone CLI to check
  system health, authenticate, manage API keys, inspect templates, create or inspect
  sandboxes, or generate browser hand-off URLs. Use only commands that exist today,
  prefer `treadstone --json ...` for machine-readable output, treat sandbox names as
  per-user labels only, and use `SANDBOX_ID` values for follow-up sandbox operations.
---

# Treadstone CLI

Use this skill to drive the Treadstone control plane through the CLI without inventing commands or guessing identifiers.

## When To Use

- The user asks you to run or explain `treadstone` CLI commands.
- The task involves Treadstone authentication, API keys, templates, sandboxes, or browser hand-off URLs.
- You need machine-readable sandbox or API key data from terminal commands.

## Task → Command

| Task | Command |
|------|---------|
| Check if the server is up | `treadstone system health` |
| Register a new account | `treadstone auth register` |
| Sign in interactively | `treadstone auth login` |
| See who is logged in | `treadstone auth whoami` |
| Create and save a reusable API key | `treadstone api-keys create --save` |
| List available sandbox templates | `treadstone --json templates list` |
| Create a sandbox and capture its ID | `treadstone --json sandboxes create --name NAME` |
| Get a browser hand-off URL for a human | `treadstone --json sandboxes web enable SANDBOX_ID` |
| Check current config / auth status | `treadstone config get` |
| Print this agent skill | `treadstone --skills` |

## Working Rules

1. Use only the canonical commands listed in the tree below.
2. Put `--json` before the subcommand whenever you need IDs, URLs, or fields to pass into later steps.
3. Protected commands use an API key first if one is provided by flag, environment variable, or local config.
4. If no API key is available, protected commands fall back to the saved login session for the active base URL.
5. `treadstone auth login` saves a local session. `treadstone auth logout` clears that saved session.
6. `treadstone api-keys create --save` stores the new key in local config for later non-interactive use.
7. Never construct browser URLs from sandbox names. Read `urls.web`, `web_url`, or `open_link` from command output.
8. `treadstone system`, `treadstone templates`, `treadstone sandboxes`, and `treadstone config`
   run their most common subcommands by default.
9. `sandboxes create` uses `--template` first, then `TREADSTONE_DEFAULT_TEMPLATE`,
   then config key `default_template`, then built-in default `aio-sandbox-tiny`.

## Canonical Command Tree

```text
treadstone system
treadstone system health

treadstone auth register
treadstone auth login
treadstone auth logout
treadstone auth whoami
treadstone auth change-password
treadstone auth resend-verification
treadstone auth users
treadstone auth delete-user

treadstone api-keys create
treadstone api-keys list
treadstone api-keys update
treadstone api-keys delete

treadstone sandboxes
treadstone sandboxes create
treadstone sandboxes list
treadstone sandboxes get
treadstone sandboxes start
treadstone sandboxes stop
treadstone sandboxes delete
treadstone sandboxes web enable
treadstone sandboxes web status
treadstone sandboxes web disable

treadstone templates
treadstone templates list

treadstone config
treadstone config set
treadstone config get
treadstone config unset
treadstone config path

treadstone guide agent
treadstone --skills
```

## Default Workflows

### Check Access And Identity

```bash
treadstone system
treadstone auth whoami
```

If authentication is missing, continue with login:

```bash
treadstone auth login --email you@example.com --password YourPass123!
```

### First-Time Interactive Onboarding

Pass `--email` and `--password` explicitly to avoid interactive prompts. If either flag is omitted,
`auth register` and `auth login` will pause and wait for keyboard input, which blocks automation.

```bash
treadstone system
treadstone auth register --email you@example.com --password YourPass123!
treadstone auth login --email you@example.com --password YourPass123!
treadstone auth whoami
```

### Create And Save A Reusable API Key

```bash
treadstone api-keys create --name automation --save
```

### Create A Sandbox, Capture Its ID, And Inspect It

```bash
treadstone --json templates
treadstone --json sandboxes create --name demo
treadstone --json sandboxes
treadstone sandboxes get SANDBOX_ID
```

Read `id` from `sandboxes create` or `sandboxes list`.
Sandbox names are only human-readable labels scoped to the current user.

### Generate A Browser Hand-Off URL For A Human

```bash
treadstone --json sandboxes web enable SANDBOX_ID
```

Read `open_link` from JSON output and report `web_url` and `expires_at`
when they are present. If `sandboxes create` already returned `urls.web`,
that URL is also safe to surface; do not synthesize it from the sandbox name.

## Identifier And Output Rules

- SANDBOX_ID arguments always require the sandbox ID, not the sandbox name.
- `sandbox.name` is a read-only display label for humans. Never use it to construct URLs,
  as a command argument, or to identify a sandbox in any follow-up operation.
- Sandbox names only need to be unique for the current user.
- Use `treadstone --json sandboxes list` or `treadstone --json sandboxes create ...` to read sandbox IDs.
- Browser hosts are based on `sandbox_id` under the hood, so `sandbox.name` is never a substitute for `sandbox.id`.
- KEY_ID arguments always require the API key ID.
- `--json` is a global flag and must appear before the subcommand.

Useful fields to extract:

- `sandboxes create` and `sandboxes get`: `id`, `urls.proxy`, `urls.web`
- `sandboxes web enable`: `open_link`, `web_url`, `expires_at`
- `api-keys create`: `key`, `id`, `saved_to_config`

## Common Recovery Paths

These are the most frequent situations where an agent gets stuck and the shortest path forward:

| Situation | Action |
|-----------|--------|
| Have a sandbox name but no ID | `treadstone --json sandboxes list`, then read `id` for that row |
| Need a valid template name | `treadstone --json templates list`, then pick a template `name` |
| Hand-off URL expired or missing | `sandboxes web disable ID` then `treadstone --json sandboxes web enable ID` |
| Command says "not authenticated" | `auth login --email … --password …` or env `TREADSTONE_API_KEY` |
| `sandboxes create` returns a name conflict | Omit `--name` and let the server generate a unique name |
| Output is hard to parse | Re-run the same command with `--json` prepended |
| Don't know the current base URL or API key status | `treadstone config get` |

## Failure Recovery

- If a protected command says no authentication is configured, run `treadstone auth login` or provide an API key.
- If a sandbox command fails with not found, verify the value comes from `sandboxes list`
  and is a sandbox ID rather than the sandbox name.
- If `sandboxes create` returns a conflict, choose a different sandbox name
  for the current user or omit `--name` and let the server generate one.
- If you need a fresh browser hand-off URL, run `treadstone sandboxes web disable SANDBOX_ID`
  and then `treadstone sandboxes web enable SANDBOX_ID`.
- If a machine-readable workflow is hard to follow from human output, rerun the command with `--json`.
"""
