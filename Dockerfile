FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY treadstone/ treadstone/
RUN uv sync --frozen --no-dev

COPY alembic/ alembic/
COPY alembic.ini .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "treadstone.main:app", "--host", "0.0.0.0", "--port", "8000"]
