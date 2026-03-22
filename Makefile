.PHONY: help install install-hooks dev test test-unit test-api test-integration test-all test-e2e test-cov lint format migrate migration downgrade gen-openapi build clean ship up down deploy-infra deploy-runtime deploy-app deploy-all undeploy-app undeploy-runtime undeploy-all restart-app kind-create kind-delete port-forward

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

# ── Code Quality ─────────────────────────────────────────────────────────────

lint: ## Run linter and formatter check
	uv run ruff check treadstone/ tests/
	uv run ruff format --check treadstone/ tests/

format: ## Auto-format code
	uv run ruff check --fix treadstone/ tests/
	uv run ruff format treadstone/ tests/

# ── Testing ──────────────────────────────────────────────────────────────────

test: ## Run tests (excludes integration)
	uv run pytest tests/ -v

test-unit: ## Run unit tests only
	uv run pytest tests/unit/ -v

test-api: ## Run API tests only
	uv run pytest tests/api/ -v

test-integration: ## Run integration tests only (needs real DB)
	uv run pytest tests/integration/ -v -m integration

test-all: ## Run all tests including integration (needs real DB)
	uv run pytest tests/ -v -m ""

test-e2e: ## Run E2E tests against deployed cluster (BASE_URL=http://localhost)
	@bash scripts/e2e-test.sh

test-cov: ## Run tests with coverage report
	uv run pytest tests/ -v --cov=treadstone --cov-report=term-missing --cov-report=html

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
	docker build -t treadstone:latest .

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/ build/ *.egg-info/ htmlcov/

# ── Deploy (Helm) ────────────────────────────────────────────────────────────

ENV ?= local

deploy-infra: ## Deploy agent-sandbox controller (once per cluster)
	helm upgrade --install agent-sandbox deploy/agent-sandbox \
		-f deploy/agent-sandbox/values-$(ENV).yaml \
		--create-namespace

deploy-runtime: ## Deploy sandbox templates + warmpool
	helm upgrade --install sandbox-runtime deploy/sandbox-runtime \
		-n treadstone -f deploy/sandbox-runtime/values-$(ENV).yaml \
		--create-namespace

deploy-app: ## Deploy Treadstone application (creates K8s secret from .env.<ENV>)
	@ENV_FILE=".env.$(ENV)"; \
	if [ ! -f "$$ENV_FILE" ]; then \
		echo "Error: $$ENV_FILE not found. Run: cp .env.example .env.$(ENV)"; \
		exit 1; \
	fi; \
	kubectl create namespace treadstone --dry-run=client -o yaml | kubectl apply -f - 2>/dev/null; \
	kubectl create secret generic treadstone-secrets \
		-n treadstone \
		--from-env-file="$$ENV_FILE" \
		--dry-run=client -o yaml | kubectl apply -f -
	helm upgrade --install treadstone deploy/treadstone \
		-n treadstone -f deploy/treadstone/values-$(ENV).yaml \
		--create-namespace

deploy-all: deploy-infra deploy-runtime deploy-app ## Deploy everything (infra → runtime → app)

restart-app: ## Rolling restart to pick up new env vars
	kubectl rollout restart deployment/treadstone -n treadstone

port-forward: ## Port-forward treadstone service to localhost:8000
	kubectl -n treadstone port-forward svc/treadstone-treadstone 8000:8000

undeploy-app: ## Undeploy Treadstone application
	helm uninstall treadstone -n treadstone 2>/dev/null || true

undeploy-runtime: ## Undeploy sandbox runtime
	helm uninstall sandbox-runtime -n treadstone 2>/dev/null || true

undeploy-all: undeploy-app undeploy-runtime ## Undeploy app + runtime (keeps infra)
	@echo "Note: agent-sandbox controller left in place. Run 'helm uninstall agent-sandbox' to remove."

# ── Environment Lifecycle ─────────────────────────────────────────────────────

up: ## Bring up full environment: make up / make up ENV=demo
	@bash scripts/up.sh $(ENV)

down: ## Tear down environment: make down / make down ENV=demo
	@bash scripts/down.sh $(ENV)

# ── Kind (local K8s) ─────────────────────────────────────────────────────────

kind-create: ## Create local Kind cluster for development
	@bash scripts/kind-setup.sh

kind-delete: ## Delete local Kind cluster
	kind delete cluster --name treadstone

# ── Git & GitHub (AI agent) ──────────────────────────────────────────────────

ship: ## AI commit & push: make ship MSG="feat: add user model"
	@if [ -z "$(MSG)" ]; then echo "Usage: make ship MSG=\"your commit message\""; exit 1; fi
	@if [ "$$(git symbolic-ref --short HEAD)" = "main" ]; then echo "Error: Cannot ship from main. Create a feature branch first."; exit 1; fi
	git add -A
	git commit -m "$(MSG)"
	git push

# ── Release ─────────────────────────────────────────────────────────────────

release: ## Tag a release: make release V=0.2.0
	@if [ -z "$(V)" ]; then echo "Usage: make release V=0.2.0"; exit 1; fi
	@if [ "$$(git symbolic-ref --short HEAD)" != "main" ]; then echo "Error: Must be on main to release."; exit 1; fi
	@echo "Tagging v$(V) and pushing — this will trigger Docker + PyPI + GitHub Release..."
	git tag "v$(V)"
	git push origin "v$(V)"
	@echo "✓ Release v$(V) triggered. Watch: gh run watch"
