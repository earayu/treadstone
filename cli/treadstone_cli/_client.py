"""HTTP client factory and local state helpers for the CLI.

Priority for API keys: CLI flags > environment variables > config file.
Saved sessions are stored separately and are only used when no API key is
available for the active base URL.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click
import httpx

CONFIG_DIR = Path.home() / ".config" / "treadstone"
CONFIG_FILE = CONFIG_DIR / "config.toml"
SESSION_FILE = CONFIG_DIR / "session.json"

_DEFAULT_BASE_URL = "https://api.treadstone-ai.dev"


def _normalize_base_url(url: str) -> str:
    return url.rstrip("/")


def _read_config() -> dict[str, str]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]
    with open(CONFIG_FILE, "rb") as f:
        data = tomllib.load(f)
    return data.get("default", {})


def _write_config(data: dict[str, dict[str, str]]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for section, kvs in data.items():
        lines.append(f"[{section}]")
        for key, value in kvs.items():
            lines.append(f'{key} = "{value}"')
        lines.append("")
    CONFIG_FILE.write_text("\n".join(lines))


def set_config_value(key: str, value: str) -> None:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

    raw: dict[str, dict[str, str]] = {}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            raw = tomllib.load(f)  # type: ignore[assignment]

    section = raw.setdefault("default", {})
    section[key] = value
    _write_config(raw)


def unset_config_value(key: str) -> bool:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

    if not CONFIG_FILE.exists():
        return False

    with open(CONFIG_FILE, "rb") as f:
        raw: dict[str, dict[str, str]] = tomllib.load(f)  # type: ignore[assignment]

    section = raw.get("default", {})
    if key not in section:
        return False

    del section[key]
    _write_config(raw)
    return True


def _read_session_store() -> dict[str, str]:
    if not SESSION_FILE.exists():
        return {}
    return json.loads(SESSION_FILE.read_text())


def _write_session_store(data: dict[str, str]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(data, indent=2, sort_keys=True))
    try:
        os.chmod(SESSION_FILE, 0o600)
    except OSError:
        pass


def save_session(base_url: str, token: str) -> None:
    sessions = _read_session_store()
    sessions[_normalize_base_url(base_url)] = token
    _write_session_store(sessions)


def clear_session(base_url: str) -> bool:
    sessions = _read_session_store()
    normalized = _normalize_base_url(base_url)
    if normalized not in sessions:
        return False
    del sessions[normalized]
    _write_session_store(sessions)
    return True


def get_saved_session(base_url: str) -> str | None:
    return _read_session_store().get(_normalize_base_url(base_url))


def get_base_url(ctx: click.Context) -> str:
    url = ctx.obj.get("base_url") or _read_config().get("base_url") or _DEFAULT_BASE_URL
    return _normalize_base_url(url)


def get_api_key(ctx: click.Context) -> str | None:
    return ctx.obj.get("api_key") or _read_config().get("api_key")


def effective_base_url() -> tuple[str, str]:
    """Return (url, source) without requiring a Click context.

    Source is one of: 'env', 'file', 'default'.
    Used for displaying configuration in help text.
    """
    env = os.environ.get("TREADSTONE_BASE_URL")
    if env:
        return _normalize_base_url(env), "env"
    cfg = _read_config().get("base_url")
    if cfg:
        return _normalize_base_url(cfg), "file"
    return _DEFAULT_BASE_URL, "default"


def effective_api_key() -> str | None:
    """Return API key without requiring a Click context."""
    return os.environ.get("TREADSTONE_API_KEY") or _read_config().get("api_key")


def effective_session(base_url: str | None = None) -> bool:
    active_base_url = _normalize_base_url(base_url or effective_base_url()[0])
    return get_saved_session(active_base_url) is not None


def get_session_token(ctx: click.Context) -> str | None:
    return get_saved_session(get_base_url(ctx))


def build_session_client(base_url: str, session_token: str) -> httpx.Client:
    return httpx.Client(base_url=_normalize_base_url(base_url), cookies={"session": session_token}, timeout=30.0)


def build_client(ctx: click.Context) -> httpx.Client:
    base_url = get_base_url(ctx)
    api_key = get_api_key(ctx)
    headers: dict[str, str] = {}
    cookies: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        session_token = get_session_token(ctx)
        if session_token:
            cookies["session"] = session_token
    return httpx.Client(base_url=base_url, headers=headers, cookies=cookies, timeout=30.0)


def require_auth(ctx: click.Context) -> httpx.Client:
    """Build client and abort if no API key or saved session is available."""
    client = build_client(ctx)
    if "Authorization" not in client.headers and not get_session_token(ctx):
        click.echo(
            "Error: No authentication configured. Run 'treadstone auth login' or set TREADSTONE_API_KEY / --api-key.",
            err=True,
        )
        sys.exit(1)
    return client
