# Why Treadstone

## What this page is for

State the platform thesis without hiding behind generic infrastructure language.

## Use this when

- You need to explain why Treadstone exists.
- You want the shortest possible argument against “just give the agent a container”.
- You need public-facing product language that still maps to the code.

## Shortest path

Read this page, then read [`core-concepts.md`](/docs/core-concepts.md). The argument only matters if the boundaries are real.

## Hard rules

- Do not describe Treadstone as “just a sandbox”.
- Do not blur control plane and data plane into one thing.
- Do not promise “agent autonomy” if a human still has to stitch the workflow together.

A raw container is not an agent platform.

A container can run code. It cannot, by itself, solve identity, tenancy, quota enforcement, template selection, runtime lifecycle, browser review, or machine-safe routing between public APIs and private execution environments. That gap is where most “agent infrastructure” falls apart.

Treadstone exists to make that gap explicit and operational:

- The control plane governs who is allowed to do what.
- The data plane routes work into the sandbox that already exists.
- The browser hand-off path turns “the agent needs a human” into a concrete URL instead of an improvised mess.

## The Attack

### “We already have Kubernetes.”

That only means you have a cluster. It does not mean you have an agent-ready control plane.

### “We can just hand the agent a VM or container.”

That gives you compute. It does not give you a contract for auth, lifecycle, scope, or review.

### “We will bolt on a browser later.”

Late browser hand-off is where bad platforms reveal themselves. If a human has to reverse-engineer the runtime state just to inspect the result, your hand-off model is broken.

## What Treadstone Adds

### Machine-safe lifecycle

Create, list, inspect, start, stop, and delete sandboxes through stable interfaces.

### Scope and auth boundaries

Control-plane routes accept session or API key. Data-plane routes accept API key only, with optional selected-sandbox grants.

### Human review without improvisation

The platform issues `web_url` and `open_link`. The caller does not invent subdomains or tokens.

### Operating model

Usage, quotas, grants, admin overrides, and self-hosting are first-class parts of the product, not afterthoughts.

## The Product Statement

Treadstone is not a generic runtime. It is the layer that lets an agent control a runtime like a product instead of treating it like a one-off shell session.

## For Agents

- Use this page for positioning only. Do not treat it as command truth.
- When you need real behavior, switch immediately to [`core-concepts.md`](/docs/core-concepts.md), [`quickstart-agent-cli.md`](/docs/quickstart-agent-cli.md), or [`api-reference.md`](/docs/api-reference.md).
