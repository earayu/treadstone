.PHONY: help install install-hooks dev test test-unit test-all test-cov lint format migrate migration downgrade gen-openapi build clean ship

# ── Development ──────────────────────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: install-hooks ## Install dependencies (first time setup)
	uv sync
	@echo "✓ Dependencies installed. Copy .env.example to .env and fill in your Neon connection string."

install-hooks: ## Install git hooks (auto-called by install)
	git config core.hooksPath .githooks
	@echo "✓ Git hooks installed (.githooks/)"

dev: ## Start local dev server with hot reload
	uv run uvicorn treadstone.main:app --reload --host 0.0.0.0 --port 8000

# ── Testing ──────────────────────────────────────────────────────────────────

test: ## Run tests (excludes integration)
	uv run pytest tests/ -v

test-unit: ## Run unit tests only
	uv run pytest tests/unit/ -v

test-all: ## Run all tests including integration (needs real DB)
	uv run pytest tests/ -v -m ""

test-cov: ## Run tests with coverage report
	uv run pytest tests/ -v --cov=treadstone --cov-report=term-missing --cov-report=html

# ── Code Quality ─────────────────────────────────────────────────────────────

lint: ## Run linter and formatter check
	uv run ruff check treadstone/ tests/
	uv run ruff format --check treadstone/ tests/

format: ## Auto-format code
	uv run ruff check --fix treadstone/ tests/
	uv run ruff format treadstone/ tests/

# ── Database ─────────────────────────────────────────────────────────────────

migrate: ## Run database migrations
	uv run alembic upgrade head

migration: ## Generate new migration (usage: make migration MSG="add users table")
	@if [ -z "$(MSG)" ]; then echo "Error: MSG is required. Usage: make migration MSG=\"add users table\""; exit 1; fi
	uv run alembic revision --autogenerate -m "$(MSG)"

downgrade: ## Rollback last migration
	uv run alembic downgrade -1

# ── OpenAPI / SDK ────────────────────────────────────────────────────────

gen-openapi: ## Export openapi.json from FastAPI app (no server needed)
	uv run python scripts/export_openapi.py

# ── Build ────────────────────────────────────────────────────────────────────

build: ## Build Docker image
	docker build -t treadstone-api:latest .

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/ build/ *.egg-info/ htmlcov/

# ── Git & GitHub (AI agent) ──────────────────────────────────────────────────

ship: ## AI commit & push: make ship MSG="feat: add user model"
	@if [ -z "$(MSG)" ]; then echo "Usage: make ship MSG=\"your commit message\""; exit 1; fi
	@if [ "$$(git symbolic-ref --short HEAD)" = "main" ]; then echo "Error: Cannot ship from main. Create a feature branch first."; exit 1; fi
	git add -A
	git commit -m "$(MSG)"
	git push
