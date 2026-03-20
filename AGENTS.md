# Treadstone

Agent-native sandbox service. Run code, build projects, deploy environments — via CLI, SDK, or REST API. Open source and self-hostable.

## Tech Stack

- Python 3.12+, FastAPI, Uvicorn, SQLAlchemy (async), asyncpg
- Database: Neon (Serverless PostgreSQL)
- Package manager: uv
- Linter/formatter: ruff
- Testing: pytest + pytest-asyncio + httpx; Hurl for E2E
- Containerization: Docker
- Orchestration: Kubernetes (Kind for dev, GKE/EKS/AKS for prod)

## Project Structure

```
treadstone/        # Application source
  main.py          # FastAPI entrypoint
  config.py        # pydantic-settings configuration
  core/            # Database engine, shared utilities
  models/          # SQLAlchemy models
  api/             # API routers
  auth/            # Authentication
  services/        # Business logic
tests/             # pytest test suites
  e2e/             # Hurl E2E tests (run against deployed cluster)
alembic/           # Database migrations
deploy/            # Helm charts, Kind config, K8s manifests
docs/              # Design docs and plans (zh-CN)
.agents/skills/    # AI Agent reusable skills
```

## Skills

Skills provide step-by-step operational guides. AGENTS.md defines rules and conventions; skills define procedures.

| Skill | When to use |
|-------|-------------|
| `dev-setup` | First-time environment setup (once per clone) |
| `dev-lifecycle` | Every feature/fix: branch, TDD, ship, PR, merge |
| `database-migration` | Adding/modifying SQLAlchemy models and Alembic migrations |
| `neon-postgres` | Neon-specific questions (branching, connection methods, SDKs) |

For K8s deployment (Kind cluster, Helm, smoke tests), see [`deploy/README.md`](deploy/README.md).

## Code Conventions

- All code comments and commit messages in English. Docs default to Chinese in `docs/zh-CN/`.
- **All GitHub-public content must be in English**: commit messages, PR titles/bodies, Issue titles/bodies, review comments, release notes.
- Async everywhere: all DB operations, HTTP calls, and API handlers must be async.
- TDD: write a failing test first, implement, verify it passes.
- DRY, YAGNI: no premature abstraction.
- All function signatures must have type hints.
- Ruff rules: E, F, I, UP (see `pyproject.toml`). Line width: 120.

## Database

- Neon Serverless PostgreSQL. Connection string injected via `TREADSTONE_DATABASE_URL` env var.
- SQLAlchemy async engine + asyncpg driver.
- Alembic migrations (Alembic uses a sync URL — `env.py` strips `+asyncpg` automatically).
- All connection strings must include `?sslmode=require`.
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
- After `make up`, run `make test-e2e` to validate the deployment. Prefer this over manual curl exploration.

## OpenAPI / SDK Generation

- Code-first: OpenAPI spec is auto-generated from FastAPI code. No static YAML to maintain.
- `make gen-openapi` exports `openapi.json` (build artifact, gitignored).
- All API routers must set `tags=["xxx"]` — SDK method names depend on tag + function name.

## Git Workflow

- **Never push directly to main.** All merges go through Pull Requests.
- Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`.
- Commit frequently. Each commit should be one small logical unit.
- Never commit `.env`, secrets, or credentials.
- PRs and Issues are automatically added to the [Project Board](https://github.com/users/earayu/projects/5/views/1) by GitHub Actions.

## Automation

- **pre-commit hook**: auto-runs `ruff format` + `ruff check` on every commit.
- **pre-push hook**: blocks direct push to main.
- **CI** (GitHub Actions): lint + test (parallel) + integration (PR only) + build. Any failure blocks merge.

## Quick Command Reference

Run `make help` for the full list. Key commands:

| Command | Purpose |
|---------|---------|
| `make dev` | Start dev server (localhost:8000, hot reload) |
| `make test` | Run tests (excludes integration) |
| `make test-e2e` | Run E2E tests against deployed cluster |
| `make lint` / `make format` | Lint check / auto-format |
| `make migrate` | Apply database migrations |
| `make migration MSG=x` | Generate a new Alembic migration |
| `make up` / `make down` | Full K8s environment up/down (see `deploy/README.md`) |
| `make ship MSG=x` | git add + commit + push (feature branches only) |
