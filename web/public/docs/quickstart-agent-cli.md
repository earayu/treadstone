# Quickstart for Agents (CLI)

## What this page is for

Give an agent the shortest reliable CLI workflow that stays in JSON, captures identifiers, and avoids guessing.

## Use this when

- You are automating Treadstone from a terminal-oriented agent runner.
- You need one path that covers auth, sandbox creation, and browser hand-off.
- You want to know which fields must be captured from output.

## Shortest path

```bash
treadstone auth login --email agent@example.com --password 'StrongPass123!'
treadstone --json api-keys create --name agent --save
treadstone --json templates list
treadstone --json sandboxes create --template aio-sandbox-tiny --name agent-demo
treadstone --json sandboxes get SANDBOX_ID
treadstone --json sandboxes web enable SANDBOX_ID
```

## Hard rules

- Prefer `--json` for any step whose output feeds another step.
- Capture `sandbox_id` from output. Do not parse it from a URL or guess it from the name.
- `treadstone skills` prints the built-in agent skill. `treadstone skills install` installs it.
- If you need proxy access, use an API key, not a saved session.

## Step 1: Authenticate

Interactive browser login:

```bash
treadstone auth login
```

Direct login:

```bash
treadstone auth login --email agent@example.com --password 'StrongPass123!'
```

## Step 2: Mint an API key

```bash
treadstone --json api-keys create --name agent --save
```

Important fields:

- `id`
- `key`
- `scope.control_plane`
- `scope.data_plane.mode`

Use `--save` if the current environment should persist the key in local CLI config. Otherwise export it explicitly:

```bash
export TREADSTONE_API_KEY="sk-..."
```

## Step 3: Create the sandbox

```bash
treadstone --json sandboxes create --template aio-sandbox-tiny --name agent-demo
```

Required fields to retain:

- `id`
- `status`
- `urls.proxy`
- `urls.web`

## Step 4: Inspect the sandbox

```bash
treadstone --json sandboxes get SANDBOX_ID
```

Use this to confirm the current state instead of assuming the create response is still current.

## Step 5: Issue a browser hand-off URL

```bash
treadstone --json sandboxes web enable SANDBOX_ID
```

Use:

- `web_url` when you need the canonical sandbox browser origin
- `open_link` when you need a human-review link

## Step 6: Install the built-in skill when needed

```bash
treadstone skills
treadstone skills install --target project
```

The built-in skill teaches other agent runners how to call the CLI without guessing identifiers or URLs.

## For Agents

- When you need a machine-safe browser URL, `open_link` is the answer.
- When you need a route map or error meaning, switch to [`api-reference.md`](/docs/api-reference.md) or [`error-reference.md`](/docs/error-reference.md).
- When you need proxy access, read [`guide-data-plane-access.md`](/docs/guide-data-plane-access.md) before you send traffic.
