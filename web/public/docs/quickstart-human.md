# Quickstart for Humans

## What this page is for

Get a human developer from zero to a browser hand-off URL with the fewest moving parts.

## Use this when

- You are testing a local or hosted Treadstone deployment yourself.
- You want a fast CLI walkthrough before reading reference docs.
- You need the minimal flow that proves auth, templates, sandbox creation, and browser hand-off all work.

## Shortest path

```bash
export TREADSTONE_BASE_URL="http://localhost"

treadstone system health
treadstone auth register --email you@example.com --password 'StrongPass123!'
treadstone auth login --email you@example.com --password 'StrongPass123!'
treadstone templates list
treadstone sandboxes create --template aio-sandbox-tiny --name human-demo
treadstone sandboxes list
treadstone sandboxes web enable SANDBOX_ID
```

## Hard rules

- Save the returned `sandbox_id` from `sandboxes list` or `--json` output.
- If sandbox creation fails with `email_verification_required`, verify the account first.
- Do not type a sandbox name into `sandboxes web enable`. It expects `sandbox_id`.

## Step 1: Check the server

```bash
treadstone system health
```

Expected result:

```json
{"status":"ok"}
```

## Step 2: Create or sign into an account

```bash
treadstone auth register --email you@example.com --password 'StrongPass123!'
treadstone auth login --email you@example.com --password 'StrongPass123!'
treadstone auth whoami
```

Use direct email and password flags when you want a short, repeatable flow. Use `treadstone auth login` without flags when you want browser login.

## Step 3: Inspect templates

```bash
treadstone templates list
```

Pick a template that the server actually offers. The platform decides the valid list.

## Step 4: Create a sandbox

```bash
treadstone --json sandboxes create --template aio-sandbox-tiny --name human-demo
```

Capture:

- `id`
- `status`
- `urls.proxy`
- `urls.web` if subdomain routing is configured

## Step 5: Open a browser hand-off URL

```bash
treadstone --json sandboxes web enable SANDBOX_ID
```

Read:

- `web_url`
- `open_link`
- `expires_at`

Open `open_link` in a browser. That is the human hand-off URL.

## Step 6: Stop or delete when done

```bash
treadstone sandboxes stop SANDBOX_ID
treadstone sandboxes delete SANDBOX_ID
```

## For Agents

- This page is the shortest human happy path, not the best non-interactive path.
- If you need machine-safe output, switch to [`quickstart-agent-cli.md`](/docs/quickstart-agent-cli.md).
