"""Build-time contracts for the browser/shell-only sandbox runtime."""

import configparser
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
IMAGE = ROOT / "deploy/sandbox-image"


def test_image_is_built_from_distribution_not_aio() -> None:
    dockerfile = (IMAGE / "Dockerfile").read_text()
    assert "FROM python:3.12-slim-bookworm" in dockerfile
    assert "RECONSTRUCTED_BASE_IMAGE" not in dockerfile
    assert "USER gem" in dockerfile
    assert "ENTRYPOINT" in dockerfile
    assert "libtk8.6" in dockerfile
    assert "XDG_SESSION_TYPE=x11" in dockerfile
    for removed in ("code-server", "jupyter", "ipykernel", "mcp-hub", "markitdown"):
        assert removed not in dockerfile.lower()
        assert removed not in (IMAGE / "requirements-python-runtime.txt").read_text().lower()


def test_only_browser_shell_support_processes_are_started() -> None:
    config = configparser.ConfigParser(interpolation=None)
    config.read(IMAGE / "supervisord.conf")
    programs = {name.removeprefix("program:") for name in config.sections() if name.startswith("program:")}
    assert programs == {"nginx", "browser", "openbox", "tigervnc", "websocat", "python-server", "gem-server"}
    assert not (ROOT / ".github/workflows/sandbox-image-reconstructed.yml").exists()
    assert not (IMAGE / "reconstructed").exists()


def test_runtime_openapi_only_advertises_supported_capabilities() -> None:
    spec = json.loads((ROOT / "scripts/sandbox_openapi_base.json").read_text())
    assert "/v1/shell/exec" in spec["paths"]
    assert "/v1/file/read" in spec["paths"]
    assert "/v1/browser/info" in spec["paths"]
    assert all(path.startswith(("/v1/shell", "/v1/file", "/v1/browser", "/v1/sandbox")) for path in spec["paths"])
    serialized = json.dumps(spec).lower()
    for removed in ("jupyter", "ipykernel", "code-server", "/v1/code", "/v1/nodejs", "markitdown"):
        assert removed not in serialized


def test_workspace_only_has_browser_and_terminal_tabs() -> None:
    page = (IMAGE / "runtime/opt/treadstone/index.html").read_text()
    assert 'id="browser-tab"' in page
    assert 'id="terminal-tab"' in page
    assert "Treadstone" in page
    assert "path: `${prefix}/websockify`" in page
    assert "`${prefix}/websockify`.replace" not in page
    for removed in ("jupyter", "code-server", "vscode"):
        assert removed not in page.lower()


def test_browser_resolution_schema_has_stable_order(monkeypatch: pytest.MonkeyPatch) -> None:
    path = IMAGE / "runtime/opt/treadstone/python/app/schemas/browser.py"
    spec = importlib.util.spec_from_file_location("_runtime_browser_schema", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    expected = ", ".join(f"{width}x{height}" for width, height in sorted(module.ALLOWED_PAIRS))
    assert module.BrowserConfigRequest.model_fields["resolution"].description.endswith(f"{expected}.")


def test_direct_browser_and_terminal_urls_remain_supported() -> None:
    nginx = (IMAGE / "runtime/opt/gem/nginx.vnc.conf").read_text()
    assert "location ~ ^/(vnc/)?websockify$" in nginx
    terminal = (IMAGE / "runtime/opt/terminal/index.html").read_text()
    assert "this.baseLocation = new URL('../', document.baseURI);" in terminal
