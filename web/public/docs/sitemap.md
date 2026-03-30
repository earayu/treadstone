# Treadstone Documentation Sitemap

This file is generated from `/docs/_manifest.json`.
Read [`/docs/index.md`](/docs/index.md) first if you are new.
Read [`/docs/ai-index.md`](/docs/ai-index.md) first if you are an agent.

## Start Here

- [Start Here](/docs/index.md): What Treadstone is, who it is for, and the shortest path to a working sandbox.
- [Why Treadstone](/docs/why-treadstone.md): Why a raw container is not enough for autonomous agents, and what Treadstone adds on top.
- [Core Concepts](/docs/core-concepts.md): The core nouns and boundaries: control plane, data plane, sandbox, template, web link, plan, and grants.

## Quickstarts

- [Quickstart for Humans](/docs/quickstart-human.md): Register, sign in, create a sandbox, and open a browser hand-off URL from the CLI.
- [Quickstart for Agents (CLI)](/docs/quickstart-agent-cli.md): The shortest non-interactive CLI path for agents: auth, create, capture sandbox_id, and issue an open_link.
- [Quickstart for Python SDK](/docs/quickstart-python-sdk.md): Use the generated Python SDK with AuthenticatedClient and typed models to create sandboxes and issue web links.
- [Quickstart for REST API](/docs/quickstart-rest-api.md): Use the control-plane REST API directly to create sandboxes and hand browser sessions to humans.

## Guides

- [Create and Manage Sandboxes](/docs/guide-sandboxes.md): Choose templates, name sandboxes correctly, use labels, and control start, stop, and delete flows.
- [Browser Handoff](/docs/guide-browser-handoff.md): Create, inspect, and revoke browser hand-off links without guessing URLs or inventing tokens.
- [Data Plane Access](/docs/guide-data-plane-access.md): Use proxy access safely with API keys, selected sandbox grants, and the control-plane/data-plane auth split.
- [Usage and Quotas](/docs/guide-usage-and-quotas.md): Read plan limits, usage summaries, compute sessions, storage ledger entries, and active grants.
- [Admin Operations](/docs/guide-admin-operations.md): Operate tier templates, user plans, grants, waitlist state, and verification tooling as an admin.

## Reference

- [CLI Reference](/docs/cli-reference.md): Real command groups, auth precedence, config resolution, JSON mode, and the built-in skills workflow.
- [API Reference](/docs/api-reference.md): Control-plane routes, proxy contract, auth model, pagination semantics, and the uniform error envelope.
- [Python SDK Reference](/docs/sdk-python-reference.md): Package layout, generated modules, sync and async call shapes, and the most useful endpoint modules.
- [Config Reference](/docs/config-reference.md): CLI config keys, environment variables, auth configuration, and sandbox subdomain settings.
- [Error Reference](/docs/error-reference.md): The JSON error envelope, common error codes, and the recovery path that maps to each failure.

## Operations

- [Self-Hosting](/docs/self-hosting.md): The deployment model, the five Helm layers, and the minimum prerequisites for self-hosting.
- [Local Development](/docs/local-development.md): Run the API and web locally, create a local cluster, and verify the stack with repo-native commands.
- [Production Deployment](/docs/production-deployment.md): Promote Treadstone beyond local Kind: leader election, OAuth callbacks, public origins, ingress, and quotas.
- [Troubleshooting](/docs/troubleshooting.md): Recover from the most common auth, quota, proxy, browser hand-off, and storage backend failures.

## AI Docs

- [AI Index](/docs/ai-index.md): Task routing for agents: which page answers create, proxy, browser hand-off, usage, admin, and self-hosting questions.
- [AI Invariants](/docs/ai-invariants.md): Hard rules for agents that must not guess IDs, URLs, auth mode, pagination model, or error semantics.
- [Documentation Sitemap](/docs/sitemap.md): The generated hierarchical index of all public docs pages and public machine-oriented endpoints.

## Public Endpoints

- [`/docs/{slug}`](/docs/index): Returns raw Markdown when the client sends `Accept: text/markdown`; otherwise redirects to `/docs?page={slug}`.
- [`/docs/sitemap.md`](/docs/sitemap.md): This complete documentation index.
- [`/llms.txt`](/llms.txt): Short machine-oriented entrypoint.
- [`/openapi.json`](/openapi.json): Generated OpenAPI document for the control plane.
