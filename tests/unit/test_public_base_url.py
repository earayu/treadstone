"""Unit tests for public_control_plane_base_url."""

from __future__ import annotations

from starlette.requests import Request


def _minimal_scope(
    *,
    scheme: str = "http",
    server: tuple[str, int] = ("test", 80),
    headers: list[tuple[bytes, bytes]] | None = None,
) -> dict:
    return {
        "type": "http",
        "asgi": {"spec_version": "2.3", "version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "root_path": "",
        "scheme": scheme,
        "query_string": b"",
        "headers": headers or [],
        "client": ("127.0.0.1", 12345),
        "server": server,
        "state": {},
    }


def test_no_forwarded_headers_uses_scope_base_url() -> None:
    from treadstone.core.public_base_url import public_control_plane_base_url

    req = Request(
        _minimal_scope(
            scheme="http",
            server=("test", 80),
            headers=[(b"host", b"test")],
        )
    )
    assert public_control_plane_base_url(req) == "http://test/"


def test_public_app_base_url_overrides_spoofed_forwarded_headers(monkeypatch) -> None:
    from treadstone.core.public_base_url import public_control_plane_base_url

    monkeypatch.setattr("treadstone.core.public_base_url.settings.app_base_url", "https://app.treadstone-ai.dev")
    req = Request(
        _minimal_scope(
            headers=[
                (b"x-forwarded-proto", b"https"),
                (b"x-forwarded-host", b"evil.example.com"),
                (b"host", b"evil.example.com"),
            ],
        )
    )
    assert public_control_plane_base_url(req) == "https://app.treadstone-ai.dev/"


def test_forwarded_https_and_host() -> None:
    from treadstone.core.public_base_url import public_control_plane_base_url

    req = Request(
        _minimal_scope(
            headers=[
                (b"x-forwarded-proto", b"https"),
                (b"x-forwarded-host", b"api.example.com"),
                (b"host", b"internal.local:8000"),
            ],
        )
    )
    assert public_control_plane_base_url(req) == "https://api.example.com/"


def test_forwarded_https_uses_host_when_no_forwarded_host() -> None:
    from treadstone.core.public_base_url import public_control_plane_base_url

    req = Request(
        _minimal_scope(
            headers=[
                (b"x-forwarded-proto", b"https"),
                (b"host", b"api.example.com"),
            ],
        )
    )
    assert public_control_plane_base_url(req) == "https://api.example.com/"


def test_forwarded_proto_list_uses_first_value() -> None:
    from treadstone.core.public_base_url import public_control_plane_base_url

    req = Request(
        _minimal_scope(
            headers=[
                (b"x-forwarded-proto", b"https, http"),
                (b"x-forwarded-host", b"api.example.com"),
            ],
        )
    )
    assert public_control_plane_base_url(req) == "https://api.example.com/"


def test_non_http_forwarded_proto_falls_back_to_request_base_url() -> None:
    from treadstone.core.public_base_url import public_control_plane_base_url

    req = Request(
        _minimal_scope(
            headers=[
                (b"x-forwarded-proto", b"h2"),
                (b"host", b"api.example.com"),
            ],
        )
    )
    assert public_control_plane_base_url(req) == str(req.base_url)


def test_local_app_base_url_still_allows_forwarded_host(monkeypatch) -> None:
    from treadstone.core.public_base_url import public_control_plane_base_url

    monkeypatch.setattr("treadstone.core.public_base_url.settings.app_base_url", "http://localhost:5173")
    req = Request(
        _minimal_scope(
            headers=[
                (b"x-forwarded-proto", b"https"),
                (b"x-forwarded-host", b"api.example.com"),
                (b"host", b"internal.local:8000"),
            ],
        )
    )
    assert public_control_plane_base_url(req) == "https://api.example.com/"
