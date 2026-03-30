# AI Invariants

## What this page is for

Give agents the hard rules that are easy to violate and expensive to recover from.

## Use this when

- You are about to automate Treadstone.
- You need a compact list of non-negotiable platform truths.
- You want rules, not narrative.

## Shortest path

Read the rules below. Then switch to the task-specific page from [`ai-index.md`](/docs/ai-index.md).

## Hard rules

- Use `sandbox_id`, not `name`, for follow-up operations.
- Browser URLs must come from `urls.web`, `web_url`, or `open_link` returned by the platform.
- Control-plane auth accepts a saved session or API key.
- Data-plane auth accepts API key only.
- Selected data-plane scope only applies to the listed sandbox IDs.
- Pagination is `limit` and `offset`.
- Sandbox creation returns `202`; do not rewrite that into `200`.
- The proxy path is `/v1/sandboxes/{sandbox_id}/proxy/{path}`.
- Browser hand-off is `/v1/sandboxes/{sandbox_id}/web-link`.

## Identity

- `name` is human-readable.
- `id` is machine-readable.
- Sandbox names only need to be unique for the current user.

## Auth

- `treadstone auth login` creates a saved control-plane session.
- API keys can be control-plane capable, data-plane capable, both, or restricted to selected sandboxes.
- If a data-plane request arrives with only a cookie session, it should fail.

## Browser Handoff

- `web_url` is the canonical browser origin.
- `open_link` is the shareable entry link.
- Do not build subdomains by concatenating the sandbox name into a hostname.

## Usage and Errors

- Read the structured error envelope. Do not pattern-match raw text only.
- Common recoverable failures include `template_not_found`, `sandbox_name_conflict`, `email_verification_required`, and `storage_backend_not_ready`.

## For Agents

- Treat this page as policy. Treat the reference pages as implementation detail.
