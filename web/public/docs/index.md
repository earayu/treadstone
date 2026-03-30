# Start Here

## What this page is for

Define Treadstone in one page. If you only read one public document before touching the CLI or API, read this one.

## Use this when

- You need the shortest explanation of what the platform does.
- You need to decide whether you are in the human path or the agent path.
- You need the first command, route, or page to open next.

## Shortest path

```bash
treadstone system health
treadstone auth login --email you@example.com --password 'StrongPass123!'
treadstone --json templates list
treadstone --json sandboxes create --name demo
treadstone --json sandboxes web enable SANDBOX_ID
```

## Hard rules

- Sandbox names are for humans. Follow-up operations use `sandbox_id`.
- Control-plane actions accept a saved session or an API key.
- Data-plane access requires an API key.
- Browser URLs come from API or CLI output. Do not construct them yourself.

Treadstone is an agent-native sandbox platform. It gives you a control plane for creating and governing sandboxes, a data plane for routing work into them, and a browser hand-off model for the moment a human has to step in.

A raw container is not an agent platform. If the runtime still needs a human to babysit auth, lifecycle, routing, quotas, and browser review, the agent is not autonomous. Treadstone closes that gap.

## Pick Your Path

### Human developer

Read:

- [`quickstart-human.md`](/docs/quickstart-human.md)
- [`guide-sandboxes.md`](/docs/guide-sandboxes.md)
- [`guide-browser-handoff.md`](/docs/guide-browser-handoff.md)

### AI agent

Read:

- [`ai-index.md`](/docs/ai-index.md)
- [`quickstart-agent-cli.md`](/docs/quickstart-agent-cli.md)
- [`ai-invariants.md`](/docs/ai-invariants.md)

### API or SDK integrator

Read:

- [`quickstart-rest-api.md`](/docs/quickstart-rest-api.md)
- [`quickstart-python-sdk.md`](/docs/quickstart-python-sdk.md)
- [`api-reference.md`](/docs/api-reference.md)

## The Three Surfaces

### CLI

Best for humans and local automation. The CLI already knows auth precedence, config resolution, JSON mode, and the built-in `skills` workflow.

### REST API

Best when you want full control over the control plane. This is the stable contract for auth, sandbox lifecycle, web links, usage, and admin actions.

### Python SDK

Best when you want generated typed models and sync or async `httpx` clients instead of hand-written requests.

## What You Actually Get

- Sandbox lifecycle: create, list, inspect, start, stop, delete.
- Template discovery: read the runtime shapes the platform will actually accept.
- Browser hand-off: issue an `open_link` when a human needs to review or decide.
- Auth and scope control: sessions, API keys, control-plane scope, selected sandbox grants.
- Metering and quotas: plans, grants, storage quotas, and admin overrides.
- Self-hosting: Kubernetes, Helm, runtime templates, API, and web.

## Next Reads

- [`why-treadstone.md`](/docs/why-treadstone.md): the product argument.
- [`core-concepts.md`](/docs/core-concepts.md): the nouns and boundaries.
- [`sitemap.md`](/docs/sitemap.md): the full index.

## For Agents

- Read [`ai-index.md`](/docs/ai-index.md) before guessing a workflow.
- Prefer the CLI quickstart when you need a short happy path.
- Prefer the API reference when you need route truth, field truth, or error truth.
- If you need a browser hand-off URL, call the platform and read `open_link` from output.
