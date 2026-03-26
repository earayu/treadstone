from __future__ import annotations

import json
import logging
from io import StringIO

import pytest
from httpx import ASGITransport, AsyncClient

from treadstone.main import app
from treadstone.middleware.request_logging import request_logger


@pytest.fixture
def request_log_stream():
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))

    original_handlers = list(request_logger.handlers)
    request_logger.handlers = [handler]
    yield stream
    request_logger.handlers = original_handlers


@pytest.mark.asyncio
async def test_health_generates_request_id_and_logs_json(request_log_stream):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Request-Id"]

    payload = json.loads(request_log_stream.getvalue().strip().splitlines()[-1])
    assert payload["event"] == "http_request"
    assert payload["request_id"] == response.headers["X-Request-Id"]
    assert payload["route_kind"] == "api"
    assert "authorization" not in request_log_stream.getvalue().lower()


@pytest.mark.asyncio
async def test_request_id_passthrough_is_logged(request_log_stream):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health", headers={"X-Request-Id": "req-health-custom"})

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "req-health-custom"

    payload = json.loads(request_log_stream.getvalue().strip().splitlines()[-1])
    assert payload["request_id"] == "req-health-custom"
