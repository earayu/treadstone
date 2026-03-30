# CLI Guide

The hosted CLI is the shortest path when a human or agent wants to drive Treadstone directly.

## Install And Point At Hosted Cloud

```bash
pip install treadstone-cli
export TREADSTONE_BASE_URL="https://api.treadstone-ai.dev"
```

## Sign In

```bash
treadstone auth login
```

Use `treadstone auth login --email you@example.com --password 'StrongPass123!'` when you need a fully non-interactive sign-in.

## Core Workflow

```bash
treadstone --json templates list
treadstone --json sandboxes create --template aio-sandbox-tiny --name demo
treadstone --json sandboxes get SANDBOX_ID
treadstone --json sandboxes web enable SANDBOX_ID
```

## Create A Reusable API Key

```bash
treadstone api-keys create --name service-key --save
```

Use saved sessions for interactive work. Use API keys for automation.

## CLI Behavior Worth Knowing

- `treadstone system health` is the connectivity check.
- `treadstone sandboxes` without a subcommand is the same as `treadstone sandboxes list`.
- Protected commands prefer API key over saved session.
- `--json` is the safe mode for automation and downstream parsing.
- `skills` exists, but it is optional. Core hosted usage does not depend on it.

> For automation: if a step needs stable fields such as `id`, `urls.proxy`, `web_url`, or `open_link`, use `--json`.

## Read Next

- [CLI Reference](/docs/cli-reference.md)
- [Create a Sandbox](/docs/create-sandbox.md)
- [Browser Handoff](/docs/browser-handoff.md)
