FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY treadstone/ treadstone/
# Runtime Swagger: merge_sandbox_paths() reads this (see treadstone/openapi_spec.py).
COPY scripts/sandbox_openapi_base.json scripts/sandbox_openapi_base.json
RUN uv sync --frozen --no-dev

COPY alembic/ alembic/
COPY alembic.ini .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "treadstone.main:app", "--host", "0.0.0.0", "--port", "8000"]
