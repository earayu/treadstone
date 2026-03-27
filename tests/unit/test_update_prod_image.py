from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "update_prod_image.py"

SAMPLE_VALUES_BACKEND = """\
replicaCount: 1

image:
  repository: ghcr.io/earayu/treadstone
  tag: 0.4.0
  pullPolicy: Always

envSecretRef: treadstone-secrets
"""

SAMPLE_VALUES_WEB = """\
replicaCount: 2

image:
  repository: ghcr.io/earayu/treadstone-web
  tag: 0.4.0
  pullPolicy: Always
"""


def _write_backend_values(tmp_path: Path, content: str = SAMPLE_VALUES_BACKEND) -> Path:
    values_path = tmp_path / "deploy" / "treadstone" / "values-prod.yaml"
    values_path.parent.mkdir(parents=True, exist_ok=True)
    values_path.write_text(content, encoding="utf-8")
    return values_path


def _write_web_values(tmp_path: Path, content: str = SAMPLE_VALUES_WEB) -> Path:
    values_path = tmp_path / "deploy" / "treadstone-web" / "values-prod.yaml"
    values_path.parent.mkdir(parents=True, exist_ok=True)
    values_path.write_text(content, encoding="utf-8")
    return values_path


def _write_all_values(tmp_path: Path) -> tuple[Path, Path]:
    return _write_backend_values(tmp_path), _write_web_values(tmp_path)


def test_update_prod_image_replaces_tag(tmp_path: Path) -> None:
    backend_path, _ = _write_all_values(tmp_path)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "v0.5.0", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    content = backend_path.read_text(encoding="utf-8")
    assert "tag: 0.5.0" in content
    assert "tag: 0.4.0" not in content


def test_update_prod_image_strips_v_prefix(tmp_path: Path) -> None:
    backend_path, _ = _write_all_values(tmp_path)

    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "v1.2.3", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "tag: 1.2.3" in backend_path.read_text(encoding="utf-8")


def test_update_prod_image_also_updates_web(tmp_path: Path) -> None:
    """Ensure the web frontend values-prod.yaml is updated alongside the backend."""
    _, web_path = _write_all_values(tmp_path)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "v0.5.0", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    content = web_path.read_text(encoding="utf-8")
    assert "tag: 0.5.0" in content
    assert "tag: 0.4.0" not in content


def test_update_prod_image_fails_when_file_missing(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "0.5.0", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "values-prod.yaml" in result.stderr
