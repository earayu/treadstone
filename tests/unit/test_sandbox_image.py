"""Build-time contracts for the browser/shell-only sandbox runtime."""

import configparser
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

from treadstone.api.schemas import SandboxDetailResponse, SandboxTemplateResponse
from treadstone.infra.services.k8s_client import FakeK8sClient

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


def test_runtime_catalog_and_api_examples_match_helm_defaults() -> None:
    values = yaml.safe_load((ROOT / "deploy/sandbox-runtime/values.yaml").read_text())
    templates = {template["name"]: template for template in values["sandboxTemplates"]}
    for template in FakeK8sClient._DEFAULT_TEMPLATES:
        assert template["image"] == values["image"]
        assert template["display_name"] == templates[template["name"]]["displayName"]
    for schema in (SandboxDetailResponse, SandboxTemplateResponse):
        assert schema.model_fields["image"].examples == [values["image"]]
    assert SandboxTemplateResponse.model_fields["display_name"].examples == [
        templates["aio-sandbox-tiny"]["displayName"]
    ]


def test_image_tool_versions_are_pinned() -> None:
    dockerfile = (IMAGE / "Dockerfile").read_text()
    for name in ("CLAUDE_CODE", "CODEX", "KIMI_CLI", "CURSOR_AGENT"):
        version = re.search(rf"^ARG {name}_VERSION=(.+)$", dockerfile, re.MULTILINE)
        assert version and version[1] != "latest", name
    assert "https://cursor.com/install" not in dockerfile
    assert 'uv tool install "kimi-cli==${KIMI_CLI_VERSION}"' in dockerfile
    for line in dockerfile.splitlines():
        if line.startswith("FROM "):
            assert "@sha256:" in line


def test_new_browser_profiles_preserve_persistent_cookies() -> None:
    preferences = json.loads((IMAGE / "runtime/opt/gem/preferences.json").read_text())
    assert preferences["profile"]["default_content_setting_values"]["cookies"] == 1


def test_publish_verifies_loaded_image_before_push_without_rebuilding() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/sandbox-image.yml").read_text())
    steps = workflow["jobs"]["docker"]["steps"]
    builds = [step for step in steps if step.get("uses", "").startswith("docker/build-push-action@")]
    assert len(builds) == 1
    assert builds[0]["with"]["load"] is True
    assert builds[0]["with"].get("push", False) is False
    verify = next(i for i, step in enumerate(steps) if "verify-sandbox-image.sh" in step.get("run", ""))
    push = next(i for i, step in enumerate(steps) if "docker push" in step.get("run", ""))
    assert steps.index(builds[0]) < verify < push
    assert "docker build" not in steps[push]["run"]
    assert "TESTED_IMAGE_ID" in steps[push]["run"]


def test_published_verification_and_benchmark_are_manual_and_read_only() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/sandbox-image.yml").read_text())
    triggers = workflow.get("on", workflow.get(True))
    assert "schedule" not in triggers
    assert triggers["workflow_dispatch"]["inputs"]["mode"]["default"] == "verify"
    for name in ("verify", "benchmark"):
        job = workflow["jobs"][name]
        assert "workflow_dispatch" in job["if"]
        assert workflow["permissions"].get("packages") != "write"
        assert "permissions" not in job or job["permissions"].get("packages") != "write"


def test_k8s_can_verify_published_image_without_rebuilding_it() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/k8s-e2e.yml").read_text())
    triggers = workflow.get("on", workflow.get(True))
    assert "sandbox_image" in triggers["workflow_dispatch"]["inputs"]
    steps = workflow["jobs"]["k8s-e2e"]["steps"]
    build = next(step for step in steps if step.get("name") == "Build sandbox runtime image")
    assert "SANDBOX_IMAGE" in build["if"]
    assert any("docker pull" in step.get("run", "") for step in steps)
    assert any("verify-sandbox-image.sh" in step.get("run", "") for step in steps)
