"""CLI behavior tests for the standalone treadstone-cli package."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

CLI_ROOT = Path(__file__).resolve().parents[2] / "cli"
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

_client = importlib.import_module("treadstone_cli._client")
cli = importlib.import_module("treadstone_cli.main").cli


class FakeResponse:
    def __init__(
        self,
        data: dict[str, Any] | None = None,
        *,
        status_code: int = 200,
        cookies: dict[str, str] | None = None,
    ):
        self._data = data or {}
        self.status_code = status_code
        self.cookies = cookies or {}
        self.text = json.dumps(self._data)

    def json(self) -> dict[str, Any]:
        return self._data


def make_fake_client(routes: dict[tuple[str, str], Any], requests: list[dict[str, Any]]):
    class FakeHTTPClient:
        def __init__(
            self,
            *,
            base_url: str,
            headers: dict[str, str] | None = None,
            cookies: dict[str, str] | None = None,
            timeout: float = 30.0,
        ) -> None:
            self.base_url = base_url.rstrip("/")
            self.headers = headers or {}
            self.cookies = dict(cookies or {})
            self.timeout = timeout

        def get(self, path: str, params: dict[str, Any] | None = None) -> FakeResponse:
            return self._request("GET", path, params=params)

        def post(self, path: str, json: dict[str, Any] | None = None) -> FakeResponse:
            return self._request("POST", path, json=json)

        def patch(self, path: str, json: dict[str, Any] | None = None) -> FakeResponse:
            return self._request("PATCH", path, json=json)

        def delete(self, path: str) -> FakeResponse:
            return self._request("DELETE", path)

        def _request(
            self,
            method: str,
            path: str,
            *,
            json: dict[str, Any] | None = None,
            params: dict[str, Any] | None = None,
        ) -> FakeResponse:
            request = {
                "method": method,
                "path": path,
                "json": json,
                "params": params,
                "headers": dict(self.headers),
                "cookies": dict(self.cookies),
                "base_url": self.base_url,
            }
            requests.append(request)
            handler = routes[(method, path)]
            if callable(handler):
                return handler(request)
            return handler

    return FakeHTTPClient


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def cli_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / ".config" / "treadstone"
    monkeypatch.setattr(_client, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(_client, "CONFIG_FILE", config_dir / "config.toml")
    monkeypatch.setattr(_client, "SESSION_FILE", config_dir / "session.json")
    return config_dir


def test_root_help_uses_system_group_and_drops_top_level_health(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "  system" in result.output
    assert "treadstone system health" in result.output
    assert "\n  health" not in result.output

    missing_alias = runner.invoke(cli, ["health"])
    assert missing_alias.exit_code != 0
    assert "No such command 'health'" in missing_alias.output


def test_guide_agent_matches_skills_flag(runner: CliRunner) -> None:
    guide_result = runner.invoke(cli, ["guide", "agent"])
    skills_result = runner.invoke(cli, ["--skills"])

    assert guide_result.exit_code == 0
    assert skills_result.exit_code == 0
    assert guide_result.output == skills_result.output
    assert guide_result.output.startswith("---\nname: treadstone-cli\n")
    assert "description:" in guide_result.output
    assert "# Treadstone CLI" in guide_result.output
    assert "SANDBOX_ID arguments always require the sandbox ID" in guide_result.output
    assert "Sandbox names only need to be unique for the current user." in guide_result.output
    assert "Never construct browser URLs from sandbox names." in guide_result.output


def test_login_saves_session_and_whoami_uses_it(
    runner: CliRunner,
    cli_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, Any]] = []

    def whoami_handler(request: dict[str, Any]) -> FakeResponse:
        assert request["headers"] == {}
        assert request["cookies"] == {"session": "sess-123"}
        return FakeResponse({"id": "usr-1", "email": "user@example.com", "role": "admin", "is_active": True})

    routes = {
        ("POST", "/v1/auth/login"): FakeResponse({"detail": "Login successful"}, cookies={"session": "sess-123"}),
        ("GET", "/v1/auth/user"): whoami_handler,
    }
    monkeypatch.setattr(_client.httpx, "Client", make_fake_client(routes, requests))

    login_result = runner.invoke(
        cli,
        ["--json", "auth", "login", "--email", "user@example.com", "--password", "Pass123!"],
    )

    assert login_result.exit_code == 0
    login_data = json.loads(login_result.output)
    assert login_data["session_saved"] is True
    assert json.loads(_client.SESSION_FILE.read_text()) == {_client._DEFAULT_BASE_URL: "sess-123"}

    whoami_result = runner.invoke(cli, ["--json", "auth", "whoami"])
    assert whoami_result.exit_code == 0
    whoami_data = json.loads(whoami_result.output)
    assert whoami_data["email"] == "user@example.com"


def test_protected_commands_prefer_api_key_over_saved_session(
    runner: CliRunner,
    cli_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _client.save_session(_client._DEFAULT_BASE_URL, "sess-123")
    _client.set_config_value("api_key", "sk-test")
    requests: list[dict[str, Any]] = []

    def whoami_handler(request: dict[str, Any]) -> FakeResponse:
        assert request["headers"]["Authorization"] == "Bearer sk-test"
        assert request["cookies"] == {}
        return FakeResponse({"id": "usr-1", "email": "api@example.com", "role": "admin", "is_active": True})

    routes = {
        ("GET", "/v1/auth/user"): whoami_handler,
    }
    monkeypatch.setattr(_client.httpx, "Client", make_fake_client(routes, requests))

    result = runner.invoke(cli, ["--json", "auth", "whoami"])

    assert result.exit_code == 0
    assert json.loads(result.output)["email"] == "api@example.com"


def test_api_key_create_save_writes_local_config(
    runner: CliRunner,
    cli_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _client.save_session(_client._DEFAULT_BASE_URL, "sess-123")
    requests: list[dict[str, Any]] = []
    routes = {
        ("POST", "/v1/auth/api-keys"): FakeResponse(
            {
                "id": "key-1",
                "name": "agent",
                "key": "sk-created",
                "scope": {"control_plane": True, "data_plane": {"mode": "all", "sandbox_ids": []}},
            }
        ),
    }
    monkeypatch.setattr(_client.httpx, "Client", make_fake_client(routes, requests))

    result = runner.invoke(cli, ["--json", "api-keys", "create", "--name", "agent", "--save"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["saved_to_config"] is True
    assert _client._read_config()["api_key"] == "sk-created"


def test_sandboxes_create_supports_auto_intervals(
    runner: CliRunner,
    cli_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _client.save_session(_client._DEFAULT_BASE_URL, "sess-123")
    requests: list[dict[str, Any]] = []

    def create_handler(request: dict[str, Any]) -> FakeResponse:
        assert request["json"]["auto_stop_interval"] == 30
        assert request["json"]["auto_delete_interval"] == 90
        assert request["json"]["labels"] == {"env": "dev"}
        return FakeResponse({"id": "sb-1", "name": "demo", "urls": {"proxy": "http://proxy", "web": None}})

    routes = {
        ("POST", "/v1/sandboxes"): create_handler,
    }
    monkeypatch.setattr(_client.httpx, "Client", make_fake_client(routes, requests))

    result = runner.invoke(
        cli,
        [
            "--json",
            "sandboxes",
            "create",
            "--template",
            "aio-sandbox-tiny",
            "--name",
            "demo",
            "--label",
            "env:dev",
            "--auto-stop-interval",
            "30",
            "--auto-delete-interval",
            "90",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["id"] == "sb-1"


def test_sandboxes_list_accepts_multiple_labels(
    runner: CliRunner,
    cli_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _client.save_session(_client._DEFAULT_BASE_URL, "sess-123")
    requests: list[dict[str, Any]] = []

    def list_handler(request: dict[str, Any]) -> FakeResponse:
        assert request["params"]["label"] == ["env:dev", "team:agent"]
        return FakeResponse({"items": [], "total": 0})

    routes = {
        ("GET", "/v1/sandboxes"): list_handler,
    }
    monkeypatch.setattr(_client.httpx, "Client", make_fake_client(routes, requests))

    result = runner.invoke(
        cli,
        ["--json", "sandboxes", "list", "--label", "env:dev", "--label", "team:agent"],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["total"] == 0


def test_sandboxes_web_commands_cover_enable_status_disable(
    runner: CliRunner,
    cli_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _client.save_session(_client._DEFAULT_BASE_URL, "sess-123")
    requests: list[dict[str, Any]] = []
    routes = {
        ("POST", "/v1/sandboxes/sb-123/web-link"): FakeResponse(
            {
                "web_url": "https://sandbox-sb-123.treadstone-ai.dev",
                "open_link": "https://sandbox-sb-123.treadstone-ai.dev/_treadstone/open?token=abc",
                "expires_at": "2026-03-31T12:00:00+00:00",
            }
        ),
        ("GET", "/v1/sandboxes/sb-123/web-link"): FakeResponse(
            {
                "web_url": "https://sandbox-sb-123.treadstone-ai.dev",
                "enabled": True,
                "expires_at": "2026-03-31T12:00:00+00:00",
                "last_used_at": None,
            }
        ),
        ("DELETE", "/v1/sandboxes/sb-123/web-link"): FakeResponse(status_code=204),
    }
    monkeypatch.setattr(_client.httpx, "Client", make_fake_client(routes, requests))

    enable_result = runner.invoke(cli, ["--json", "sandboxes", "web", "enable", "sb-123"])
    status_result = runner.invoke(cli, ["--json", "sandboxes", "web", "status", "sb-123"])
    disable_result = runner.invoke(cli, ["--json", "sandboxes", "web", "disable", "sb-123"])

    assert enable_result.exit_code == 0
    assert status_result.exit_code == 0
    assert disable_result.exit_code == 0
    assert json.loads(enable_result.output)["web_url"].endswith("sandbox-sb-123.treadstone-ai.dev")
    assert json.loads(enable_result.output)["open_link"].endswith("token=abc")
    assert json.loads(status_result.output)["enabled"] is True
    assert json.loads(disable_result.output)["sandbox_id"] == "sb-123"
