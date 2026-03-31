---
name: treadstone-docs-maintenance
description: Maintain Treadstone's public documentation system and copy contract. Use when adding, rewriting, reorganizing, validating, or reviewing public docs in `web/public/docs`, the docs manifest, `llms.txt`, `sitemap.md`, docs landing copy, or AI-facing documentation paths. Also use when planning doc IA, fixing stale commands or routes, tightening docs tone, or keeping human and agent documentation aligned with the current code.
---

# Treadstone Docs Maintenance

Maintain Treadstone's public docs as a product surface, not as a markdown dump. Keep them short, exact, code-grounded, and useful to both AI agents and human developers.

## Keep One Source of Truth

- Treat `web/public/docs/_manifest.json` as the canonical docs inventory.
- Do not introduce a second slug list in frontend or backend code.
- Keep these files aligned:
  - `web/public/docs/_manifest.json`
  - `treadstone/docs_manifest.py`
  - `scripts/generate_public_docs.py`
  - `treadstone/api/docs.py`
  - `web/src/pages/public/docs.tsx`
- Regenerate derived outputs after manifest or page changes:

```bash
uv run python scripts/generate_public_docs.py
```

Do not hand-edit generated public outputs unless you are also changing the generator:

- `web/public/docs/sitemap.md`
- `web/public/llms.txt`

## Write for Two Readers at Once

Public docs serve two readers:

- AI agents that consume raw Markdown and need stable commands, routes, fields, and invariants.
- Human developers that want the answer fast, not a tutorial novel.

Write so both can succeed from the same page:

- Put the shortest working path near the top.
- Put critical identifiers, commands, routes, and fields before background explanation.
- Include a `For Agents` section on every public page.
- Keep page intros short enough that a human can scan them and an agent can parse them cheaply.

## Follow the Page Contract

Every public docs page should open with these sections, in this order:

- `What this page is for`
- `Use this when`
- `Shortest path`
- `Hard rules`

Every public docs page should also include:

- one main happy-path example at most
- one agent-oriented example at most
- a `For Agents` section

Do not start pages with long background sections. The first screen should explain what the page is for and how to use it.

## Preserve the Information Architecture

Public docs sections are fixed unless there is a deliberate structural change:

- `Start Here`
- `Guides`
- `Reference`
- `Operations`
- `AI Docs`

Prefer adding pages inside the existing IA before inventing a new category.

Use page type appropriately:

- `Start Here`: positioning, product argument, core concepts
- `Guides`: task completion (shortest runnable paths live in **Integrate** and **Core Workflows**)
- `Reference`: factual contracts only
- `Operations`: self-hosting, local dev, deployment, troubleshooting
- `AI Docs`: task routing and hard invariants

## Match Tone to Page Type

Use a sharp, direct tone. Optimize for impact and clarity, not politeness padding.

Always:

- write directly
- cut filler
- prefer commands, routes, and fields over abstract prose
- make the value proposition obvious

Positioning pages may be opinionated and a little aggressive when the claim is real:

- `A raw container is not an agent platform.`
- `IDs are for machines. Names are for humans.`
- `If a human has to babysit the runtime, the agent is not autonomous.`

But keep the aggression disciplined:

- no empty swagger
- no hype without code-backed substance
- no marketing language inside reference pages

Reference pages must be cold, factual, and contract-oriented.

## Keep Facts Grounded in the Current Code

Never copy old public docs forward without re-checking the implementation.

Verify commands, routes, fields, and behavior against the current code and tests:

- API routes: `treadstone/api/*.py`
- auth boundaries: `treadstone/api/deps.py`
- sandbox lifecycle and web link flows: `treadstone/api/sandboxes.py`, `treadstone/services/sandbox_service.py`
- CLI commands: `cli/treadstone_cli/*.py`
- SDK module paths: `sdk/python/treadstone_sdk`
- E2E reality: `tests/e2e/*.hurl`
- API tests: `tests/api/*.py`

Prefer current code and tests over old docs, README fragments, or memory.

## Protect Key Treadstone Insights

Preserve these documentation-level truths:

- Treadstone is not "just sandboxes"; it is control plane + data plane + browser hand-off + metering/admin/self-hosting.
- Control plane and data plane are different surfaces with different auth rules.
- `sandbox_id` is the machine identifier; `name` is only a human label.
- Browser URLs come from platform output, not user-side string construction.
- Public docs are English-first.
- Internal Chinese docs under `docs/zh-CN/` remain internal and should not be mixed into public docs navigation.

## Keep the Public Surface Consistent

When public docs change, check whether these entry points also need updates:

- `web/src/pages/public/landing.tsx`
- `web/src/components/layout/public-layout.tsx`
- `web/public/robots.txt`
- `web/public/llms.txt`
- `web/public/docs/sitemap.md`

Landing snippets and CTA links must not drift behind the docs.

## Preferred Workflow

1. Read the relevant code and tests before writing.
2. Update the page Markdown in `web/public/docs/`.
3. Update `web/public/docs/_manifest.json` if the page set, slug, order, title, or section changes.
4. Regenerate public docs outputs.
5. Verify the docs path for both web readers and raw Markdown consumers.
6. Check landing and nav copy if the docs entrypoint or naming changed.

## Validate Before Shipping

For docs-system or public-docs changes, run the lightest checks that prove the docs are still coherent:

```bash
uv run python scripts/generate_public_docs.py --check
uv run pytest tests/unit/test_docs_manifest.py tests/api/test_docs_api.py -q
cd web && pnpm test
cd web && pnpm lint
git diff --check
```

If the docs page implementation changed, also run:

```bash
cd web && pnpm build
```

## Do Not Do These Things

- Do not add verbose "overview" prose that delays the first real command or concept.
- Do not invent a second docs inventory outside `_manifest.json`.
- Do not describe stale routes like `/v1/auth/me` or `/web/enable`.
- Do not put marketing copy into reference pages.
- Do not mix internal design docs with the public docs IA.
- Do not let `landing.tsx` advertise examples that no longer match the product.

## Output Standard

The finished docs should make a competent reader feel two things immediately:

- `I know exactly what this platform does.`
- `I know exactly what to run or call next.`
