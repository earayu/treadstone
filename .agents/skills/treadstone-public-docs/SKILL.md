---
name: treadstone-public-docs
description: Maintain Treadstone's public documentation system and copy contract. Use when adding, rewriting, reorganizing, validating, or reviewing public docs in `web/public/docs`, the docs manifest, `llms.txt`, `sitemap.md`, `sitemap.xml`, `robots.txt`, docs landing copy, or AI-facing documentation paths—including control-plane vs data-plane narratives. Also use when planning doc IA (Diátaxis-style page typing, WeSQL-like progressive structure), fixing stale commands or routes, tightening prose, or aligning human and agent docs with the current code. See also `openapi-spec-conventions` for the three-tier OpenAPI story.
---

# Treadstone Public Docs

Maintain Treadstone's public docs as a **product surface**, not a markdown dump. Keep them short, exact, code-grounded, and useful to both AI agents and human developers.

Quality bar blends external references (adapt ideas, do not paste long text):

- **[What makes documentation good](https://developers.openai.com/cookbook/articles/what_makes_documentation_good)** (OpenAI): skimmable structure, clear sentences, reader empathy.
- **[Diátaxis](https://diataxis.fr/)**: four user intents—learning, task, facts, understanding—mapped to distinct doc **forms**; do not blur them on one page.
- **[Doc co-authoring](https://github.com/anthropics/skills/blob/main/skills/doc-coauthoring/SKILL.md)** (Anthropic): context → draft → **reader test** before shipping large rewrites.

**WeSQL-inspired structure (documentation shape only):** progressive paths (intro / map → hands-on steps → feature topics with prerequisites → cold reference) resemble how strong infra docs teach—**not** a claim about database technology. Treadstone uses Neon PostgreSQL for the control-plane DB; that is unrelated to this pattern name.

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
- `web/public/sitemap.xml`
- `web/public/robots.txt`

## Diátaxis → Treadstone IA

Pick **one primary intent per page** and match headings to it:

| Diátaxis form | Reader intent | Treadstone home (typical) |
|---------------|---------------|----------------------------|
| **Tutorial** | Learn by doing, stepwise | Short first-run paths in **Get Started** / **Integrate** |
| **How-to guide** | Complete a task | **Core Workflows**, **Integrate** guides |
| **Reference** | Exact facts | **Reference** |
| **Explanation** | Understand why / design | **Get Started** (Overview), short prose—**not** inside reference tables |

If a page drifts, split or move content—**reference stays cold and contract-shaped**.

## Prose Quality (OpenAI checklist, condensed)

**Skimmable:** Informative section titles (not vague nouns). Short paragraphs; **topic sentence first**. Put takeaways before detail. Bullets/tables where they beat prose; **bold** sparingly for scan-worthy facts.

**Clear:** Short, right-branching sentences. Unambiguous wording. Avoid **this/that** across sentences without a named referent. Stay **consistent** with terminology and casing.

**Broadly helpful:** Simple words; spell out abbreviations on first use when it helps ESL readers. Examples stay minimal-dependency and **never teach bad habits** (e.g. secrets in code). Avoid presuming the reader's mental state—use neutral task phrasing ("To call X, …").

## Control Plane vs Data Plane (document both clearly)

Treadstone is **two planes** with different auth and clients:

| Plane | Role | Typical access |
|-------|------|------------------|
| **Control plane** | Lifecycle, identity, keys, usage | Session or API key for `/v1/...` (see public Reference) |
| **Data plane** | Workloads *inside* a running sandbox | API key with **data-plane** scope; traffic to `urls.proxy` / `/v1/sandboxes/{sandbox_id}/proxy/...` |

When adding or rewriting public docs on runtime work inside sandboxes, **ground copy in**:

- **[examples/README.md](examples/README.md)** — architecture diagram, `treadstone_sdk` vs `agent_sandbox.Sandbox`, `urls.proxy` wiring.
- **[examples/04_data_plane.py](examples/04_data_plane.py)** — shell, file, browser, Jupyter; data-plane key usage.

**OpenAPI / Swagger (production):** Full HTTP contract including sandbox runtime paths merged under the proxy prefix lives in the **full** OpenAPI served by the API (e.g. `GET https://api.treadstone-ai.dev/openapi.json`, interactive `https://api.treadstone-ai.dev/docs`). Implementation: `merge_sandbox_paths` in [`treadstone/openapi_spec.py`](treadstone/openapi_spec.py). Swagger groups many operations under **Sandbox: …** tags.

**SDK note:** `openapi-public.json` (used for `treadstone-sdk` generation) **does not** include merged sandbox-runtime paths—by design. Tell readers: **browse data-plane HTTP operations in hosted Swagger or full `openapi.json`**; use the Python SDK where generated, plus examples, for call patterns. Deeper conventions: [`.agents/skills/openapi-spec-conventions/SKILL.md`](../openapi-spec-conventions/SKILL.md).

## Write for Two Readers at Once

- AI agents need stable **commands, routes, fields, invariants**, and machine-readable structure.
- Humans need the **fastest correct path** and skimmable headings.

On every public page: shortest path near the top; identifiers before narrative; a **`For Agents`** section.

## Follow the Page Contract

Open with these sections, in order:

- `What this page is for`
- `Use this when`
- `Shortest path`
- `Hard rules`

Also include: at most one main happy-path example, at most one agent-oriented example, and `For Agents`. Do not open with long background.

## Manifest Sections (`_manifest.json`)

Structural changes need deliberate review. Current order:

- **Get Started** — positioning, overview, map to the rest
- **Core Workflows** — sandboxes, auth, limits, browser handoff
- **Integrate** — CLI, REST, SDK, MCP guides
- **Reference** — API, CLI, SDK, errors (contracts only)

Prefer new pages inside this IA before inventing categories.

## Match Tone to Page Type

Sharp and direct. Prefer commands, routes, and fields over abstract prose. Positioning may be opinionated when backed by product truth; **Reference** stays neutral—no marketing.

## Keep Facts Grounded in the Current Code

Verify against code and tests:

- API routes: `treadstone/api/*.py`
- Auth / data plane: `treadstone/api/deps.py`, `treadstone/api/sandbox_proxy.py`
- Sandboxes / browser: `treadstone/api/sandboxes.py`, `treadstone/services/sandbox_service.py`
- CLI: `cli/treadstone_cli/*.py`
- SDK: `sdk/python/treadstone_sdk`
- E2E: `tests/e2e/*.hurl`; API tests: `tests/api/*.py`

Prefer code and tests over memory or old README fragments.

## Protect Key Treadstone Insights

- Treadstone is control plane + data plane + browser hand-off + metering/admin/self-hosting—not "just containers."
- Control plane vs data plane: **different auth rules**; document both.
- `sandbox_id` is the machine identifier; `name` is a human label.
- Browser and proxy URLs come from **platform output** (`urls.proxy`, `web_url`, `open_link`)—do not document hand-built hostnames.
- Public docs are **English-first**. Internal Chinese under `docs/zh-CN/` stays out of public nav.

## Keep the Public Surface Consistent

When docs change, check entry points and CTAs:

- `web/src/pages/public/landing.tsx`
- `web/src/components/layout/public-layout.tsx`
- `web/public/robots.txt`, `web/public/llms.txt`, `web/public/sitemap.xml`, `web/public/docs/sitemap.md`

Landing copy must not drift from the product.

## Optional Workflow for Large Rewrites

1. **Context** — Audience, success criteria, re-read code/tests.
2. **Draft by intent** — One Diátaxis intent per section; keep reference free of tutorial prose.
3. **Reader test** — Questions a newcomer would ask; fix hidden assumptions (fresh-context read or separate short agent session with Markdown only).

Skip for tiny edits.

## Preferred Workflow

1. Read code/tests for the behavior you document.
2. Edit Markdown under `web/public/docs/`.
3. Update `_manifest.json` if slug, section, order, title, or summary changes.
4. Run `uv run python scripts/generate_public_docs.py`.
5. Verify web docs and raw Markdown consumers (`/docs`, `.md` routes, `llms.txt`).
6. Update landing/nav if entrypoints changed.

## Validate Before Shipping

```bash
uv run python scripts/generate_public_docs.py --check
uv run pytest tests/unit/test_docs_manifest.py tests/api/test_docs_api.py -q
cd web && pnpm test
cd web && pnpm lint
git diff --check
```

If the docs UI changed:

```bash
cd web && pnpm build
```

## Do Not

- Delay the first actionable line with a long "overview."
- Maintain a second inventory besides `_manifest.json`.
- Document stale routes (audit current routers).
- Put marketing tone in **Reference**.
- Mix internal design docs into public IA.
- Let `landing.tsx` promise flows the product no longer supports.
- **Smush Diátaxis types** (e.g. tutorial prose inside error-code tables).
- **Conflate** full OpenAPI (with merged sandbox paths) with `openapi-public.json` / SDK coverage—call out the split explicitly when documenting HTTP.

## Output Standard

After changes, a competent reader should feel:

- They know **what Treadstone is for** (including control vs data plane).
- They know **exactly what to run, call, or configure next**—and agents can extract the same facts mechanically.
