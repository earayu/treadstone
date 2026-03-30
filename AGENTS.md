# Treadstone

Agent-native sandbox platform for AI agents. Run code, build projects, deploy environments, and hand off browser sessions via CLI, SDK, or REST API. Open source and self-hostable.

## Start Here

Use the matching local skill before you act:

| If you need to... | Use |
|-------|-------------|
| Set up this repo for the first time | `dev-setup` |
| Make any shippable change | `dev-lifecycle` |
| Add or change SQLAlchemy models / Alembic migrations | `database-migration` |
| Answer Neon-specific questions or plan Neon usage | `neon-postgres` |
| Audit a subsystem against the current code and write a detailed report | `system-audit-report` |
| Refresh an existing audit report against the latest code | `audit-report-refresh` |
| Trace runtime architecture and end-to-end data flow | `architecture-data-flow-trace` |

Skills live under `.agents/skills/*/SKILL.md`. AGENTS.md defines repo facts and guardrails; skills define procedures.

## Tech Stack

- Python 3.12+, FastAPI, Uvicorn, SQLAlchemy (async), asyncpg
- Database: Neon (Serverless PostgreSQL)
- Package managers: uv (Python), pnpm (web)
- Lint/format: ruff (Python), ESLint (web)
- Testing: pytest + pytest-asyncio + httpx; Hurl for E2E
- Containerization: Docker
- Orchestration: Kubernetes (Kind for dev, GKE/EKS/AKS for prod)

## Project Structure

```
treadstone/        # Server application source
  main.py          # FastAPI entrypoint
  config.py        # pydantic-settings configuration
  core/            # Database engine, shared utilities
  models/          # SQLAlchemy models
  api/             # API routers
  auth/            # Authentication
  services/        # Business logic
cli/               # CLI package (standalone, published as treadstone-cli)
  treadstone_cli/  # CLI source (click + httpx + rich)
sdk/python/        # Python SDK (published as treadstone-sdk)
tests/             # pytest test suites
  api/             # FastAPI route tests via ASGITransport
  unit/            # Pure logic / model / helper tests
  integration/     # Real DB tests, excluded by default
  e2e/             # Hurl E2E tests (run against deployed cluster)
alembic/           # Database migrations
deploy/            # Helm charts, Kind config, K8s manifests
docs/              # Design docs and plans (zh-CN)
scripts/           # Helper scripts (release, install, deploy, E2E)
.agents/skills/    # AI Agent reusable skills
```

## Skills

| Skill | When to use |
|-------|-------------|
| `dev-setup` | First-time environment setup (once per clone) |
| `dev-lifecycle` | Every feature/fix: branch, TDD, ship, PR, merge |
| `database-migration` | Adding/modifying SQLAlchemy models and Alembic migrations |
| `neon-postgres` | Neon-specific questions (branching, connection methods, SDKs) |
| `system-audit-report` | First-pass or general subsystem audits grounded in the current code |
| `audit-report-refresh` | Re-auditing a subsystem and updating an existing report against the latest code |
| `architecture-data-flow-trace` | Tracing runtime architecture, state transitions, and end-to-end data flow |

For K8s deployment (Kind cluster, Helm, smoke tests), see [`deploy/README.md`](deploy/README.md).

## Code Conventions

- All code comments and commit messages in English. Docs default to Chinese in `docs/zh-CN/`.
- **All GitHub-public content must be in English**: commit messages, PR titles/bodies, Issue titles/bodies, review comments, release notes.
- Root-facing docs such as `README.md`, `AGENTS.md`, and `.agents/skills/*/SKILL.md` should stay concise and easy for both humans and agents to scan.
- Async everywhere: all DB operations, HTTP calls, and API handlers must be async.
- TDD: write a failing test first, implement, verify it passes.
- DRY, YAGNI: no premature abstraction.
- All function signatures must have type hints.
- When adding or changing auth, admin, API key, sandbox lifecycle, browser hand-off, or other user-facing control-plane features, update Audit Log coverage and structured request logging in the same change.
- Ruff rules: E, F, I, UP (see `pyproject.toml`). Line width: 120.

## Error Handling

All API errors must return a consistent JSON envelope:

```json
{"error": {"code": "snake_case_code", "message": "Human-readable detail.", "status": 409}}
```

Rules:

- **Never raise bare `HTTPException`** — always use a `TreadstoneError` subclass from `treadstone/core/errors.py`.
- **Wrap every `session.commit()`** that can fail with a DB constraint (unique, FK, check) in `try/except IntegrityError`, rollback, and raise a domain-specific `TreadstoneError`.
- **Catch external-service failures** (K8s API, HTTP proxy) — convert them to `TreadstoneError` subclasses, never let raw `ConnectionError`, `TimeoutError`, etc. escape to the client.
- **Use the right HTTP status code**: 400 `BadRequestError` for invalid input, 404 `NotFoundError`, 409 `ConflictError` / `SandboxNameConflictError` for conflicts, 422 `ValidationError` for schema issues.
- **Global fallback handlers** in `main.py` catch `RequestValidationError` (422), `IntegrityError` (409), and `Exception` (500), guaranteeing the envelope format even for unexpected errors. Service-level handlers should still be preferred for domain-specific messages.
- **Always log before returning 5xx**: use `logger.exception(...)` so the stack trace is captured server-side, but never expose internal details to the client.

## Database

- Neon Serverless PostgreSQL. Connection string injected via `TREADSTONE_DATABASE_URL` env var.
- SQLAlchemy async engine + asyncpg driver.
- Alembic migrations (Alembic uses a sync URL — `env.py` strips `+asyncpg` automatically).
- All connection strings must include `?sslmode=require`.
- For local `make dev-api`, use `.env`. For Kubernetes deployment, use `.env.<ENV>` such as `.env.local`.
- For model design conventions and the migration workflow, see the `database-migration` skill.

## Testing

- pytest-asyncio with `asyncio_mode = "auto"` (no need for `@pytest.mark.asyncio`).
- API tests use `httpx.AsyncClient` + `ASGITransport` (no real server needed).
- Use `monkeypatch` for env vars in tests — never depend on `.env` files.
- Test directory structure:
  - `tests/unit/` — pure logic, no IO
  - `tests/api/` — API route tests via ASGITransport
  - `tests/integration/` — requires real DB, marked `@pytest.mark.integration`, excluded by default
  - `tests/e2e/*.hurl` — E2E tests against a deployed cluster, written in [Hurl](https://hurl.dev) (run with `make test-e2e`)
- Shared fixtures live in `tests/conftest.py`.
- `make test` excludes integration tests via pytest config; use `make test-integration` or `make test-all` when real DB coverage is needed.
- After `make up`, run `make test-e2e` to validate the deployment. Prefer this over manual curl exploration.

## OpenAPI / SDK Generation

- Code-first: OpenAPI spec is auto-generated from FastAPI code. No static YAML to maintain.
- `make gen-openapi` exports `openapi.json` (build artifact, gitignored).
- All API routers must set `tags=["xxx"]` — SDK method names depend on tag + function name.
- **Reviewability:** API-facing changes often regenerate large, mechanical diffs. Prefer either:
  - **Two commits on the same branch:** (1) hand-written work — `treadstone/`, `tests/`, `web/` app code, `alembic/`, plus `web/src/api/schema.d.ts` from `make gen-web-types` when the web app needs new types; (2) `chore: regenerate Python SDK from OpenAPI` touching **`sdk/python/`** only via `make gen-sdk-python`. Or:
  - **One commit** if splitting is impractical — then state in the PR body that **`sdk/python/**` and `web/src/api/schema.d.ts` are generated only** (no manual edits in those paths), so reviewers can skim them.

## Git Workflow

- **Never push directly to main.** All merges go through Pull Requests.
- Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`.
- Commit frequently. Each commit should be one small logical unit.
- Never commit `.env`, secrets, or credentials.
- PRs and Issues are automatically added to the [Project Board](https://github.com/users/earayu/projects/5/views/1) by GitHub Actions.

## Release

Two-step flow: **bump** (on feature branch) → **release** (on main).

1. `git checkout -b chore/release-x.y.z && make bump V=x.y.z` — bumps version in `pyproject.toml` (server, CLI, SDK) + `uv.lock`, commits and pushes.
2. Open a PR, wait for CI, merge.
3. `git checkout main && git pull && make release V=x.y.z` — tags `vx.y.z` and pushes the tag (no branch push).
4. Tag push triggers [`.github/workflows/release.yml`](.github/workflows/release.yml): Docker image → GHCR, `treadstone-cli` + `treadstone-sdk` → PyPI, CLI binaries + install scripts → GitHub Release assets.
5. After Release succeeds, [`.github/workflows/update-prod-image.yml`](.github/workflows/update-prod-image.yml) auto-updates `deploy/treadstone/values-prod.yaml` image tag and commits to `main`.

- **Agents:** Use `make bump V=…` then `make release V=…`. Do not hand-craft `git tag` / `git push origin v…` or `gh release create` unless fixing a broken release.

## Automation

- **pre-commit hook**: auto-runs `ruff format` + `ruff check` on every commit.
- **pre-push hook**: blocks direct push to main.
- **CI** (GitHub Actions): lint + test + openapi + build on pushes/PRs, plus integration on PRs. Any failure blocks merge.
- **CD** (`.github/workflows/cd.yml`): pushes the `main` image to GHCR on changes to deployable server files.
- **Release** (`.github/workflows/release.yml`): publishes tagged releases and GitHub Release assets on `v*` tags.
- **Update Prod Image** (`.github/workflows/update-prod-image.yml`): after Release succeeds, auto-updates `values-prod.yaml` image tag and commits to `main`.

## Quick Command Reference

Run `make help` for the full list. Key commands:

| Command | Purpose |
|---------|---------|
| `make install` | Install Python/web dependencies and git hooks |
| `make dev-api` | Start API dev server (localhost:8000, hot reload) |
| `make dev-web` | Start web dev server (localhost:5173, hot reload) |
| `make test` | Run tests (excludes integration) |
| `make test-all` | Run all tests including integration |
| `make test-e2e` | Run E2E tests against deployed cluster |
| `make lint` / `make format-py` | Repo lint checks / Python auto-format |
| `make migrate` | Apply database migrations |
| `make migration MSG=x` | Generate a new Alembic migration |
| `make gen-openapi` | Export `openapi.json` from the FastAPI app |
| `make gen-web-types` / `make gen-sdk-python` | Generate client artifacts from OpenAPI |
| `make up` / `make down` | Full K8s environment up/down (see `deploy/README.md`) |
| `make ship MSG=x` | git add + commit + push (feature branches only) |
| `make bump V=x.y.z` | Bump version files, commit + push (feature branches only) |
| `make release V=x.y.z` | Tag `vx.y.z` on `main` and push tag (triggers full release pipeline) |
