FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# hatchling validates readme from pyproject.toml during the install phase
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

COPY treadstone/ treadstone/
COPY alembic/ alembic/
COPY alembic.ini .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "treadstone.main:app", "--host", "0.0.0.0", "--port", "8000"]
