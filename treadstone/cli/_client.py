"""HTTP client factory for CLI commands.

Priority: CLI flags > environment variables > config file.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click
import httpx

CONFIG_DIR = Path.home() / ".config" / "treadstone"
CONFIG_FILE = CONFIG_DIR / "config.toml"

_DEFAULT_BASE_URL = "http://localhost:8000"


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


def get_base_url(ctx: click.Context) -> str:
    url = ctx.obj.get("base_url") or _read_config().get("base_url") or _DEFAULT_BASE_URL
    return url.rstrip("/")


def get_api_key(ctx: click.Context) -> str | None:
    return ctx.obj.get("api_key") or _read_config().get("api_key")


def effective_base_url() -> tuple[str, str]:
    """Return (url, source) without requiring a Click context.

    Source is one of: 'env', 'file', 'default'.
    Used for displaying configuration in help text.
    """
    env = os.environ.get("TREADSTONE_BASE_URL")
    if env:
        return env.rstrip("/"), "env"
    cfg = _read_config().get("base_url")
    if cfg:
        return cfg.rstrip("/"), "file"
    return _DEFAULT_BASE_URL, "default"


def effective_api_key() -> str | None:
    """Return API key without requiring a Click context."""
    return os.environ.get("TREADSTONE_API_KEY") or _read_config().get("api_key")


def build_client(ctx: click.Context) -> httpx.Client:
    base_url = get_base_url(ctx)
    api_key = get_api_key(ctx)
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return httpx.Client(base_url=base_url, headers=headers, timeout=30.0)


def require_auth(ctx: click.Context) -> httpx.Client:
    """Build client and abort if no API key is configured."""
    client = build_client(ctx)
    if "Authorization" not in client.headers:
        click.echo("Error: No API key configured. Set TREADSTONE_API_KEY or use --api-key.", err=True)
        sys.exit(1)
    return client
