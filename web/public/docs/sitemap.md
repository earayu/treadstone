# Treadstone Documentation Sitemap

This file is generated from `/docs/_manifest.json`.
Read [`/docs/index.md`](/docs/index.md) first if you are new.

## Get Started

- [Overview](/docs/index.md): What Treadstone is, who it is for, and how to choose between the Console, CLI, REST API, and Python SDK.
- [Quickstart](/docs/quickstart.md): The fastest hosted path from account creation to a running sandbox and a shareable browser handoff URL.

## Core Workflows

- [Create a Sandbox](/docs/create-sandbox.md): Choose a template, set lifecycle controls, attach storage when needed, and capture the fields you will use next.
- [Browser Handoff](/docs/browser-handoff.md): Generate, inspect, and revoke browser handoff URLs without inventing tokens or guessing subdomain URLs.
- [API Keys & Auth](/docs/api-keys-auth.md): Understand session login, API keys, control-plane access, data-plane access, and selected sandbox grants.
- [Usage & Limits](/docs/usage-limits.md): Read plan limits, compute remaining, storage quota, allowed templates, concurrency limits, and billing-period status.

## Integrate

- [CLI Guide](/docs/cli-guide.md): Use the hosted CLI for login, sandbox lifecycle, browser handoff, and API key management with machine-safe JSON output.
- [REST API Guide](/docs/rest-api-guide.md): Call the hosted control plane directly with API keys to create sandboxes, issue browser handoff links, and inspect usage.
- [Python SDK Guide](/docs/python-sdk-guide.md): Use the generated Python SDK with AuthenticatedClient and typed request models for the hosted API.

## Reference

- [API Reference](/docs/api-reference.md): The user-facing control-plane contract: auth, sandboxes, browser handoff, proxy, usage endpoints, pagination, and error shape.
- [CLI Reference](/docs/cli-reference.md): Root options, command groups, auth precedence, JSON mode, config keys, and the exact hosted CLI surface.
- [Python SDK Reference](/docs/python-sdk-reference.md): Real import paths, generated endpoint modules, request and response models, and sync or async call shapes.
- [Error Reference](/docs/error-reference.md): The stable JSON error envelope, common public error codes, and the recovery step that matches each failure.

## Public Endpoints

- [`/docs/{slug}`](/docs/index): Returns raw Markdown when the client sends `Accept: text/markdown`; otherwise redirects to `/docs?page={slug}`.
- [`/docs/sitemap.md`](/docs/sitemap.md): This complete documentation index.
- [`/llms.txt`](/llms.txt): Short machine-oriented entrypoint.
- [`/openapi.json`](/openapi.json): Generated OpenAPI document for the control plane.
