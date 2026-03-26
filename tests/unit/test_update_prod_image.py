from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "update_prod_image.py"

SAMPLE_VALUES = """\
replicaCount: 1

image:
  repository: ghcr.io/earayu/treadstone
  tag: 0.4.0
  pullPolicy: Always

envSecretRef: treadstone-secrets
"""


def _write_values(tmp_path: Path, content: str = SAMPLE_VALUES) -> Path:
    values_path = tmp_path / "deploy" / "treadstone" / "values-prod.yaml"
    values_path.parent.mkdir(parents=True, exist_ok=True)
    values_path.write_text(content, encoding="utf-8")
    return values_path


def test_update_prod_image_replaces_tag(tmp_path: Path) -> None:
    values_path = _write_values(tmp_path)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "v0.5.0", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    content = values_path.read_text(encoding="utf-8")
    assert "tag: 0.5.0" in content
    assert "tag: 0.4.0" not in content


def test_update_prod_image_strips_v_prefix(tmp_path: Path) -> None:
    values_path = _write_values(tmp_path)

    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "v1.2.3", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "tag: 1.2.3" in values_path.read_text(encoding="utf-8")


def test_update_prod_image_fails_when_file_missing(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "0.5.0", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "values-prod.yaml" in result.stderr
