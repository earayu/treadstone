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
_auth_cmd = importlib.import_module("treadstone_cli.auth")
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

        def get(
            self, path: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None
        ) -> FakeResponse:
            return self._request("GET", path, params=params, extra_headers=headers)

        def post(
            self, path: str, json: dict[str, Any] | None = None, headers: dict[str, str] | None = None
        ) -> FakeResponse:
            return self._request("POST", path, json=json, extra_headers=headers)

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
            extra_headers: dict[str, str] | None = None,
        ) -> FakeResponse:
            merged_headers = {**self.headers, **(extra_headers or {})}
            request = {
                "method": method,
                "path": path,
                "json": json,
                "params": params,
                "headers": merged_headers,
                "cookies": dict(self.cookies),
                "base_url": self.base_url,
            }
            requests.append(request)
            handler = routes.get((method, path))
            if handler is None:
                for (rm, rp), rh in routes.items():
                    if rm == method and _path_matches(rp, path):
                        handler = rh
                        break
            if handler is None:
                raise KeyError(f"No route for {method} {path}")
            if callable(handler):
                return handler(request)
            return handler

    return FakeHTTPClient


def _path_matches(pattern: str, path: str) -> bool:
    """Simple wildcard match: '/v1/auth/cli/flows/*/status' matches '/v1/auth/cli/flows/clf123/status'."""
    pattern_parts = pattern.split("/")
    path_parts = path.split("/")
    if len(pattern_parts) != len(path_parts):
        return False
    return all(pp == "*" or pp == rp for pp, rp in zip(pattern_parts, path_parts))


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


def test_root_help_surfaces_common_nested_commands(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "Command Reference:" in result.output
    assert "auth login" in result.output
    assert "config get" in result.output
    assert "sandboxes create" in result.output
    assert "sandboxes web enable" in result.output


def test_skills_prints_agent_guide(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["skills"])

    assert result.exit_code == 0
    assert result.output.startswith("---\nname: treadstone-cli\n")
    assert "description:" in result.output
    assert "# Treadstone CLI" in result.output
    assert "SANDBOX_ID arguments always require the sandbox ID" in result.output
    assert "Sandbox names only need to be unique for the current user." in result.output
    assert "Never construct browser URLs from sandbox names." in result.output


def test_skills_install_default_target(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    agents_skills_dir = tmp_path / ".agents" / "skills"
    monkeypatch.setattr(
        "treadstone_cli.skills_cmd._TARGETS",
        {
            "agents": agents_skills_dir,
            "cursor": tmp_path / ".cursor" / "skills",
            "codex": tmp_path / ".codex" / "skills",
            "project": tmp_path / ".agents" / "skills",
        },
    )

    result = runner.invoke(cli, ["skills", "install"])

    assert result.exit_code == 0
    dest = agents_skills_dir / "treadstone-cli" / "SKILL.md"
    assert dest.exists()
    content = dest.read_text(encoding="utf-8")
    assert content.startswith("---\nname: treadstone-cli\n")
    assert "Installed:" in result.output


def test_skills_install_cursor_target(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cursor_skills_dir = tmp_path / ".cursor" / "skills"
    monkeypatch.setattr(
        "treadstone_cli.skills_cmd._TARGETS",
        {
            "agents": tmp_path / ".agents" / "skills",
            "cursor": cursor_skills_dir,
            "codex": tmp_path / ".codex" / "skills",
            "project": tmp_path / ".agents" / "skills",
        },
    )

    result = runner.invoke(cli, ["skills", "install", "--target", "cursor"])

    assert result.exit_code == 0
    dest = cursor_skills_dir / "treadstone-cli" / "SKILL.md"
    assert dest.exists()


def test_skills_install_custom_dir(runner: CliRunner, tmp_path: Path) -> None:
    custom_dir = tmp_path / "my-skills"

    result = runner.invoke(cli, ["skills", "install", "--dir", str(custom_dir)])

    assert result.exit_code == 0
    dest = custom_dir / "treadstone-cli" / "SKILL.md"
    assert dest.exists()
    content = dest.read_text(encoding="utf-8")
    assert "# Treadstone CLI" in content


def test_skills_install_creates_missing_dirs(runner: CliRunner, tmp_path: Path) -> None:
    nested_dir = tmp_path / "a" / "b" / "c"

    result = runner.invoke(cli, ["skills", "install", "--dir", str(nested_dir)])

    assert result.exit_code == 0
    assert (nested_dir / "treadstone-cli" / "SKILL.md").exists()


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


def test_sandboxes_create_uses_builtin_default_template_when_omitted(
    runner: CliRunner,
    cli_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _client.save_session(_client._DEFAULT_BASE_URL, "sess-123")
    requests: list[dict[str, Any]] = []

    def create_handler(request: dict[str, Any]) -> FakeResponse:
        assert request["json"]["template"] == "aio-sandbox-tiny"
        return FakeResponse({"id": "sb-default", "name": "demo", "template": request["json"]["template"]})

    routes = {
        ("POST", "/v1/sandboxes"): create_handler,
    }
    monkeypatch.setattr(_client.httpx, "Client", make_fake_client(routes, requests))

    result = runner.invoke(cli, ["--json", "sandboxes", "create", "--name", "demo"])

    assert result.exit_code == 0
    assert json.loads(result.output)["template"] == "aio-sandbox-tiny"


def test_sandboxes_create_uses_configured_default_template_when_omitted(
    runner: CliRunner,
    cli_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _client.save_session(_client._DEFAULT_BASE_URL, "sess-123")
    _client.set_config_value("default_template", "aio-sandbox-medium")
    requests: list[dict[str, Any]] = []

    def create_handler(request: dict[str, Any]) -> FakeResponse:
        assert request["json"]["template"] == "aio-sandbox-medium"
        return FakeResponse({"id": "sb-config", "name": "demo", "template": request["json"]["template"]})

    routes = {
        ("POST", "/v1/sandboxes"): create_handler,
    }
    monkeypatch.setattr(_client.httpx, "Client", make_fake_client(routes, requests))

    result = runner.invoke(cli, ["--json", "sandboxes", "create", "--name", "demo"])

    assert result.exit_code == 0
    assert json.loads(result.output)["template"] == "aio-sandbox-medium"


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


def test_sandboxes_group_defaults_to_list(
    runner: CliRunner,
    cli_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _client.save_session(_client._DEFAULT_BASE_URL, "sess-123")
    requests: list[dict[str, Any]] = []
    routes = {
        ("GET", "/v1/sandboxes"): FakeResponse({"items": [], "total": 0}),
    }
    monkeypatch.setattr(_client.httpx, "Client", make_fake_client(routes, requests))

    result = runner.invoke(cli, ["--json", "sandboxes"])

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


def test_config_group_defaults_to_get(runner: CliRunner, cli_state: Path) -> None:
    _client.set_config_value("base_url", "https://example.com")
    _client.set_config_value("default_template", "aio-sandbox-medium")

    result = runner.invoke(cli, ["config"])

    assert result.exit_code == 0
    assert "base_url = https://example.com" in result.output
    assert "default_template = aio-sandbox-medium" in result.output


# ── CLI browser OAuth login flow tests ──────────────────────────


def _make_browser_flow_routes(
    poll_responses: list[FakeResponse] | None = None,
) -> dict[tuple[str, str], Any]:
    """Build routes for a browser login flow with configurable poll responses."""
    poll_iter = iter(poll_responses or [FakeResponse({"status": "approved"})])

    return {
        ("POST", "/v1/auth/cli/flows"): FakeResponse(
            {
                "flow_id": "clf-test",
                "flow_secret": "secret-abc",
                "browser_url": "http://test/v1/auth/cli/login?flow_id=clf-test",
                "expires_at": "2099-01-01T00:00:00Z",
                "poll_interval": 2,
            }
        ),
        ("GET", "/v1/auth/cli/flows/*/status"): lambda _req: next(poll_iter),
        ("POST", "/v1/auth/cli/flows/*/exchange"): FakeResponse({"session_token": "jwt-token-123"}),
    }


def test_browser_login_success_saves_session(
    runner: CliRunner,
    cli_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, Any]] = []
    routes = _make_browser_flow_routes()
    monkeypatch.setattr(_client.httpx, "Client", make_fake_client(routes, requests))
    monkeypatch.setattr(_auth_cmd, "webbrowser", type("FakeWB", (), {"open": staticmethod(lambda url: True)})())
    monkeypatch.setattr(_auth_cmd.time, "sleep", lambda _: None)

    result = runner.invoke(cli, ["auth", "login"])

    assert result.exit_code == 0
    assert "Login successful" in result.output
    assert json.loads(_client.SESSION_FILE.read_text()) == {_client._DEFAULT_BASE_URL: "jwt-token-123"}

    poll_req = next(r for r in requests if r["method"] == "GET" and "status" in r["path"])
    assert poll_req["headers"]["X-Flow-Secret"] == "secret-abc"


def test_browser_login_webbrowser_open_failure_still_prints_url(
    runner: CliRunner,
    cli_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, Any]] = []
    routes = _make_browser_flow_routes()
    monkeypatch.setattr(_client.httpx, "Client", make_fake_client(routes, requests))

    def failing_open(url: str) -> None:
        raise OSError("no browser")

    monkeypatch.setattr(_auth_cmd, "webbrowser", type("FakeWB", (), {"open": staticmethod(failing_open)})())
    monkeypatch.setattr(_auth_cmd.time, "sleep", lambda _: None)

    result = runner.invoke(cli, ["auth", "login"])

    assert result.exit_code == 0
    assert "Could not open browser" in result.output
    assert "http://test/v1/auth/cli/login?flow_id=clf-test" in result.output
    assert "Login successful" in result.output


def test_browser_login_flow_expired_exits_with_error(
    runner: CliRunner,
    cli_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, Any]] = []
    routes = _make_browser_flow_routes(poll_responses=[FakeResponse({"status": "expired"})])
    monkeypatch.setattr(_client.httpx, "Client", make_fake_client(routes, requests))
    monkeypatch.setattr(_auth_cmd, "webbrowser", type("FakeWB", (), {"open": staticmethod(lambda url: True)})())
    monkeypatch.setattr(_auth_cmd.time, "sleep", lambda _: None)

    result = runner.invoke(cli, ["auth", "login"])

    assert result.exit_code != 0
    assert "expired" in result.output


def test_browser_login_flow_failed_exits_with_error(
    runner: CliRunner,
    cli_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, Any]] = []
    routes = _make_browser_flow_routes(poll_responses=[FakeResponse({"status": "failed"})])
    monkeypatch.setattr(_client.httpx, "Client", make_fake_client(routes, requests))
    monkeypatch.setattr(_auth_cmd, "webbrowser", type("FakeWB", (), {"open": staticmethod(lambda url: True)})())
    monkeypatch.setattr(_auth_cmd.time, "sleep", lambda _: None)

    result = runner.invoke(cli, ["auth", "login"])

    assert result.exit_code != 0
    assert "failed" in result.output


def test_json_login_without_credentials_returns_error(
    runner: CliRunner,
    cli_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = runner.invoke(cli, ["--json", "auth", "login"])

    assert result.exit_code != 0
    data = json.loads(result.output)
    assert "error" in data
    assert "interactive" in data["error"].lower()


def test_direct_login_with_email_password_still_works(
    runner: CliRunner,
    cli_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, Any]] = []
    routes = {
        ("POST", "/v1/auth/login"): FakeResponse({"detail": "Login successful"}, cookies={"session": "direct-sess"}),
    }
    monkeypatch.setattr(_client.httpx, "Client", make_fake_client(routes, requests))

    result = runner.invoke(cli, ["auth", "login", "--email", "u@b.com", "--password", "Pass123!"])

    assert result.exit_code == 0
    assert "Login successful" in result.output
    assert json.loads(_client.SESSION_FILE.read_text()) == {_client._DEFAULT_BASE_URL: "direct-sess"}


def test_browser_login_polls_pending_then_approved(
    runner: CliRunner,
    cli_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI correctly waits through pending polls until approved."""
    requests: list[dict[str, Any]] = []
    routes = _make_browser_flow_routes(
        poll_responses=[
            FakeResponse({"status": "pending"}),
            FakeResponse({"status": "pending"}),
            FakeResponse({"status": "approved"}),
        ]
    )
    monkeypatch.setattr(_client.httpx, "Client", make_fake_client(routes, requests))
    monkeypatch.setattr(_auth_cmd, "webbrowser", type("FakeWB", (), {"open": staticmethod(lambda url: True)})())

    sleep_calls: list[float] = []
    monkeypatch.setattr(_auth_cmd.time, "sleep", lambda s: sleep_calls.append(s))

    result = runner.invoke(cli, ["auth", "login"])

    assert result.exit_code == 0
    assert "Login successful" in result.output
    assert len(sleep_calls) == 3
    poll_requests = [r for r in requests if r["method"] == "GET" and "status" in r["path"]]
    assert len(poll_requests) == 3
