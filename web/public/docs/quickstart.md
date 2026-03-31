# Quickstart

## What this page is for

Get from zero to a **running sandbox** in a few commands: install the CLI, sign in, create an API key if you need automation, then create a sandbox. Use this as the bridge into **Core Workflows** (lifecycle, auth detail, limits).

## Use this when

- You are new to Treadstone and want a **shortest path** before reading task-focused pages.
- You need install commands and the minimum auth steps; deeper behavior lives in [CLI Guide](/docs/cli-guide.md).

## Shortest path

1. Create an account: open [/auth/sign-up](/auth/sign-up) (or use `treadstone auth register` after install).
2. Install the CLI (pick one):

```bash
curl -fsSL https://treadstone-ai.dev/install.sh | sh
# or: pip install treadstone-cli
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

5. List templates and create a sandbox:

```bash
treadstone templates list
treadstone sandboxes create --template aio-sandbox-tiny --name demo
```

6. Continue with [Sandbox Lifecycle](/docs/sandbox-lifecycle.md) for list, inspect, stop, start, and delete.

For **JSON-shaped output** (agents, CI), add `--json` to commands. Full install options, global flags, and credential rules: [CLI Guide](/docs/cli-guide.md).

## Hard rules

- Use **`sandbox_id`** from platform output for follow-up API or CLI calls. Treat **`name`** as a human label only.
- Read **`urls.proxy`**, **`web_url`**, and **`open_link`** from API or `--json` output. **Do not** construct proxy or browser URLs by hand.
- **Control plane** (this CLI by default) talks to `/v1/...` on the API host. **Data plane** traffic goes through each sandbox’s **`urls.proxy`** (see [REST API Guide](/docs/rest-api-guide.md)). More on runtime access is coming in the data-plane docs.

## For Agents

- Prefer `treadstone --json` for machine parsing; scrape `sandbox_id`, `urls.proxy`, `open_link` from responses.
- After install, the same flow applies: register/login if needed, `api-keys create --save`, `templates list`, `sandboxes create` with a template id from `templates list`.
- Stable control-plane reference: [API Reference](/docs/api-reference.md); CLI surface: [CLI Reference](/docs/cli-reference.md).

## Read next

- [Sandbox Lifecycle](/docs/sandbox-lifecycle.md)
- [API Keys & Auth](/docs/api-keys-auth.md)
- [CLI Guide](/docs/cli-guide.md)
