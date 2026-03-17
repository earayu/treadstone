.PHONY: help dev test lint format migrate migration build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Start local dev server with hot reload
	uv run uvicorn treadstone.main:app --reload --host 0.0.0.0 --port 8000

test: ## Run all tests
	uv run pytest tests/ -v

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
	rm -rf dist/ build/ *.egg-info/
