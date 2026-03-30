# AI Index

## What this page is for

Route agents to the right page with minimal search.

## Use this when

- You are an agent entering the docs for the first time.
- You need to know which page answers a concrete task.
- You want to avoid scanning the full sitemap.

## Shortest path

- Need to create a sandbox: [`quickstart-agent-cli.md`](/docs/quickstart-agent-cli.md), [`quickstart-rest-api.md`](/docs/quickstart-rest-api.md)
- Need to hand a browser to a human: [`guide-browser-handoff.md`](/docs/guide-browser-handoff.md)
- Need proxy access: [`guide-data-plane-access.md`](/docs/guide-data-plane-access.md)
- Need route truth: [`api-reference.md`](/docs/api-reference.md)
- Need CLI truth: [`cli-reference.md`](/docs/cli-reference.md)

## Hard rules

- Read [`ai-invariants.md`](/docs/ai-invariants.md) before automating a multi-step flow.
- Use quickstarts for happy paths and reference pages for contracts.
- Prefer the platform response over any assumption you made one step earlier.

## Task Routing

### Create a sandbox

- CLI: [`quickstart-agent-cli.md`](/docs/quickstart-agent-cli.md)
- REST: [`quickstart-rest-api.md`](/docs/quickstart-rest-api.md)
- Concepts: [`core-concepts.md`](/docs/core-concepts.md)

### Create a browser hand-off URL

- Guide: [`guide-browser-handoff.md`](/docs/guide-browser-handoff.md)
- Route contract: [`api-reference.md`](/docs/api-reference.md)

### Send traffic into the sandbox

- Guide: [`guide-data-plane-access.md`](/docs/guide-data-plane-access.md)
- Hard rules: [`ai-invariants.md`](/docs/ai-invariants.md)

### Work with quotas or plans

- User view: [`guide-usage-and-quotas.md`](/docs/guide-usage-and-quotas.md)
- Admin view: [`guide-admin-operations.md`](/docs/guide-admin-operations.md)

### Self-host or debug the platform

- Ops entry: [`self-hosting.md`](/docs/self-hosting.md)
- Local dev: [`local-development.md`](/docs/local-development.md)
- Production: [`production-deployment.md`](/docs/production-deployment.md)
- Recovery: [`troubleshooting.md`](/docs/troubleshooting.md)

## Preferred Reading Order

1. [`index.md`](/docs/index.md)
2. [`ai-invariants.md`](/docs/ai-invariants.md)
3. One quickstart
4. One guide
5. One reference page

## For Agents

- If the task is operational, you probably need a guide.
- If the task is contractual, you probably need a reference page.
- If the task is ambiguous, start with [`core-concepts.md`](/docs/core-concepts.md).
