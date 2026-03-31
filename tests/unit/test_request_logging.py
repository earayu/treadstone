from __future__ import annotations

import pytest

from treadstone.middleware.request_logging import _should_emit_http_request_log


@pytest.mark.parametrize(
    ("method", "path", "status", "expected"),
    [
        ("GET", "/health", 200, False),
        ("GET", "/health", 204, False),
        ("GET", "/health", 500, True),
        ("GET", "/health", 404, True),
        ("POST", "/health", 200, True),
        ("GET", "/v1/foo", 200, True),
    ],
)
def test_should_emit_http_request_log(method: str, path: str, status: int, expected: bool) -> None:
    assert _should_emit_http_request_log(method, path, status) is expected
