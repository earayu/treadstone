"""Static guide text for agent-oriented CLI usage."""

from __future__ import annotations

AGENT_GUIDE = """Treadstone Agent Guide

Purpose
  Treadstone CLI manages control-plane access, sandboxes, templates, and API keys.
  This guide only describes commands that exist today.

Canonical command tree
  treadstone system health
  treadstone auth register
  treadstone auth login
  treadstone auth whoami
  treadstone api-keys create|list|update|delete
  treadstone sandboxes create|list|get|start|stop|delete
  treadstone sandboxes web enable|status|disable
  treadstone templates list
  treadstone config set|get|unset|path
  treadstone guide agent

Authentication rules
  1. Protected commands use an API key first if one is provided by flag, env var, or local config.
  2. If no API key is available, protected commands fall back to the saved login session for the active base URL.
  3. `treadstone auth login` saves a local session. `treadstone auth logout` clears that saved session.
  4. `treadstone api-keys create --save` stores the new key in local config for later non-interactive use.

Identifier rules
  - SANDBOX_ID arguments always require the sandbox ID, not the sandbox name.
  - Use `treadstone --json sandboxes list` or `treadstone --json sandboxes create ...` to read sandbox IDs.
  - KEY_ID arguments always require the API key ID.

Common workflows
  1. First-time interactive onboarding
     treadstone system health
     treadstone auth register --email you@example.com --password YourPass123!
     treadstone auth login --email you@example.com --password YourPass123!
     treadstone auth whoami

  2. Create and save a reusable API key
     treadstone api-keys create --name automation --save

  3. Create a sandbox and inspect it
     treadstone templates list
     treadstone sandboxes create --template aio-sandbox-tiny --name demo
     treadstone sandboxes list
     treadstone sandboxes get SANDBOX_ID

  4. Generate a browser hand-off URL for a human
     treadstone sandboxes web enable SANDBOX_ID
     Read the `open_link` field from JSON output or the "open_link" row in human output.

JSON usage
  - Pass `--json` before the command, for example: `treadstone --json sandboxes list`
  - Useful fields:
    - sandboxes create/get: `id`, `urls.proxy`, `urls.web`
    - sandboxes web enable: `open_link`, `web_url`, `expires_at`
    - api-keys create: `key`, `id`, `saved_to_config`

Failure recovery
  - If a protected command says no authentication is configured, run `treadstone auth login` or provide an API key.
  - If a sandbox command fails with not found, verify the value is a sandbox ID from `sandboxes list`, not the name.
  - If you need a fresh browser hand-off URL, run `treadstone sandboxes web enable SANDBOX_ID` again.
"""
