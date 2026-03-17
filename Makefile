.PHONY: help dev test test-unit test-all test-cov lint format migrate migration build clean ship

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Start local dev server with hot reload
	uv run uvicorn treadstone.main:app --reload --host 0.0.0.0 --port 8000

test: ## Run tests (excludes integration)
	uv run pytest tests/ -v

test-unit: ## Run unit tests only
	uv run pytest tests/unit/ -v

test-all: ## Run all tests including integration (needs real DB)
	uv run pytest tests/ -v -m ""

test-cov: ## Run tests with coverage report
	uv run pytest tests/ -v --cov=treadstone --cov-report=term-missing --cov-report=html

lint: ## Run linter and formatter check
	uv run ruff check treadstone/ tests/
	uv run ruff format --check treadstone/ tests/

format: ## Auto-format code
	uv run ruff check --fix treadstone/ tests/
	uv run ruff format treadstone/ tests/

migrate: ## Run database migrations
	uv run alembic upgrade head

migration: ## Generate new migration (usage: make migration MSG="add users table")
	uv run alembic revision --autogenerate -m "$(MSG)"

build: ## Build Docker image
	docker build -t treadstone-api:latest .

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/ build/ *.egg-info/ htmlcov/

ship: ## AI commit & push: make ship MSG="feat: add user model"
	@if [ -z "$(MSG)" ]; then echo "Usage: make ship MSG=\"your commit message\""; exit 1; fi
	git add -A
	git commit -m "$(MSG)"
	git push
