# Quickstart

## What this page is for

Get from zero to a **running sandbox** in a few commands: install the CLI, sign in, create an API key if you need automation, then create a sandbox. Use this as the bridge into **core workflows** (lifecycle, auth detail, limits).

## Use this when

- You are new to Treadstone and want a **shortest path** before reading task-focused pages.
- You need install commands and the minimum auth steps; deeper behavior lives in the [CLI Guide](/docs/cli-guide.md).

## Shortest path

1. Create an account: open [/auth/sign-up](/auth/sign-up) (or use `treadstone auth register` after install).

2. Install the CLI (pick one):

   ```bash
   # macOS / Linux:
   curl -fsSL https://treadstone-ai.dev/install.sh | sh
   # Windows (PowerShell):
   # irm https://treadstone-ai.dev/install.ps1 | iex
   # or:
   # pip install treadstone-cli
   ```

3. Sign in and verify:

   ```bash
   treadstone auth login
   treadstone auth whoami
   ```

4. Create an API key and save it for scripts (optional but typical for automation):

   ```bash
   treadstone api-keys create --name local --save
   ```

5. Create a sandbox:

   ```bash
   treadstone sandboxes create --template aio-sandbox-tiny --name demo
   ```

   Note **`sandbox_id`** in the output, or add **`--json`** and read **`id`**—see [CLI Guide](/docs/cli-guide.md) for output shape.

6. Inspect that sandbox (status, URLs, and other fields):

   ```bash
   treadstone sandboxes get <sandbox_id>
   ```

7. **Done** — you have a working sandbox. When you need to stop, start, list, or delete sandboxes, follow [Sandbox Lifecycle](/docs/sandbox-lifecycle.md).

## Next steps (pick what you need)

- **Operate sandboxes** — list, inspect, stop, start, delete: [Sandbox Lifecycle](/docs/sandbox-lifecycle.md).
- **What Web, MCP, and Proxy mean** — and how **`urls.*`** fits with control vs data plane: [Sandbox endpoints](/docs/sandbox-endpoints.md).
- **Keys, sessions, and scopes** — [API Keys & Auth](/docs/api-keys-auth.md).
- **CLI behavior** — structured output (`--json`), config, install: [CLI Guide](/docs/cli-guide.md).

## Pitfalls to avoid

- Use **`sandbox_id`** from CLI or API output for follow-up calls. Treat **`name`** as a human label only.
- **Do not** invent proxy or browser URLs. Copy **`urls.*`** (and handoff fields like **`open_link`** when applicable) from **`sandboxes get`** or API responses — see [Sandbox endpoints](/docs/sandbox-endpoints.md).

## Agents and automation

- Use machine-readable CLI output when parsing results (`--json`); fields to scrape include **`id`**, **`urls.*`**, **`open_link`** (see [CLI Guide](/docs/cli-guide.md)).
- Typical sequence after install: register or login if needed, **`api-keys create --save`**, **`templates list`**, **`sandboxes create`** using a template id from **`templates list`**.
- Contract references: [API Reference](/docs/api-reference.md) (HTTP), [CLI Reference](/docs/cli-reference.md) (commands).

## Read next

- [Sandbox Lifecycle](/docs/sandbox-lifecycle.md)
- [Sandbox endpoints](/docs/sandbox-endpoints.md)
- [API Keys & Auth](/docs/api-keys-auth.md)
- [CLI Guide](/docs/cli-guide.md)
