from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "set_release_versions.py"


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_set_release_versions_updates_all_release_version_files(tmp_path: Path) -> None:
    _write_file(
        tmp_path / "pyproject.toml",
        """
[project]
name = "treadstone"
version = "0.1.0"
""".strip(),
    )
    _write_file(
        tmp_path / "cli" / "pyproject.toml",
        """
[project]
name = "treadstone-cli"
version = "0.1.0"
""".strip(),
    )
    _write_file(
        tmp_path / "sdk" / "python" / "pyproject.toml",
        """
[tool.poetry]
name = "treadstone-sdk"
version = "0.1.0"
""".strip(),
    )
    _write_file(
        tmp_path / "web" / "package.json",
        """
{
  "name": "treadstone-web",
  "version": "0.1.0",
  "private": true
}
""".strip(),
    )
    _write_file(
        tmp_path / "web" / "src" / "lib" / "app-version.ts",
        'export const APP_VERSION = "0.1.0";',
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "0.3.4", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert 'version = "0.3.4"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.3.4"' in (tmp_path / "cli" / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.3.4"' in (tmp_path / "sdk" / "python" / "pyproject.toml").read_text(encoding="utf-8")
    assert '"version": "0.3.4"' in (tmp_path / "web" / "package.json").read_text(encoding="utf-8")
    assert 'APP_VERSION = "0.3.4"' in (tmp_path / "web" / "src" / "lib" / "app-version.ts").read_text(encoding="utf-8")


def test_set_release_versions_fails_when_a_target_file_is_missing(tmp_path: Path) -> None:
    _write_file(
        tmp_path / "pyproject.toml",
        """
[project]
name = "treadstone"
version = "0.1.0"
""".strip(),
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "0.3.4", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "cli/pyproject.toml" in result.stderr
