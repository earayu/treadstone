"""Tests for sandbox name validation and documentation."""

from __future__ import annotations

from pathlib import Path

from treadstone.api.schemas import CreateSandboxRequest


def test_create_sandbox_schema_documents_name_rules() -> None:
    name_schema = CreateSandboxRequest.model_json_schema()["properties"]["name"]

    assert "1-55 characters" in name_schema["description"]
    assert "lowercase letters, numbers, or hyphens" in name_schema["description"]
    assert "sandbox-{name}" in name_schema["description"]


def test_cli_source_documents_sandbox_name_rules() -> None:
    source = (Path(__file__).resolve().parents[2] / "cli" / "treadstone_cli" / "sandboxes.py").read_text()

    assert "1-55 characters" in source
    assert "lowercase letters" in source
    assert "numbers, or hyphens" in source
    assert "sandbox-{name}" in source
