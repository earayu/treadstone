# CLI Guide

The CLI is the shortest path when a human or agent wants to drive Treadstone without writing HTTP clients or SDK code.

## Install

```bash
pip install treadstone-cli
export TREADSTONE_BASE_URL="https://api.treadstone-ai.dev"
```

## Sign In

```bash
treadstone auth login
```

This opens a browser-based login flow. For fully non-interactive environments — scripts, CI, agents — pass credentials directly:

```bash
treadstone auth login --email you@example.com --password 'StrongPass123!'
```

## Core Workflow

```bash
treadstone --json templates list                                           # see what your plan allows
treadstone --json sandboxes create --template aio-sandbox-tiny --name demo  # create; save `id` from response
treadstone --json sandboxes get SANDBOX_ID                                 # inspect current state
treadstone --json sandboxes web enable SANDBOX_ID                          # generate handoff URL; share `open_link`
```

Capture `id` from `sandboxes create`. Every follow-up command uses it, not `name`.

## Create A Reusable API Key

```bash
treadstone api-keys create --name service-key --save
```

Use a saved session for interactive work. Use an API key for automation — scripts, agents, and scheduled tasks should not depend on browser login sessions. The `--save` flag writes the key to the local config so subsequent commands pick it up automatically.

## Behavior Worth Knowing

- `treadstone system health` checks connectivity to the hosted API. There is no top-level `health` command.
- `treadstone sandboxes` without a subcommand is the same as `treadstone sandboxes list`.
- When both an API key and a saved session exist, the API key wins.
- `--json` outputs stable structured data safe for downstream parsing. Always use it in scripts.
- `treadstone skills` exists but is optional; core hosted usage does not depend on it.

> For automation: use `--json` whenever another tool, agent, or script will consume the result. Parse `id`, `urls.proxy`, `web_url`, and `open_link` from that output.

## Read Next

- [CLI Reference](/docs/cli-reference.md)
- [Create a Sandbox](/docs/create-sandbox.md)
- [Browser Handoff](/docs/browser-handoff.md)
