from __future__ import annotations

import json
from pathlib import Path

import pytest

from treadstone.docs_manifest import (
    DOCS_DIR,
    LLMS_PATH,
    DocManifestEntry,
    load_docs_manifest,
    render_llms_txt,
    render_sitemap_markdown,
    validate_manifest_entries,
)


def _entry(**overrides: object) -> DocManifestEntry:
    payload = {
        "slug": "index",
        "title": "Overview",
        "section": "Get Started",
        "order": 10,
        "summary": "What Treadstone is and how to get started.",
        "default": True,
        "llm_priority": 100,
        "aliases": [],
    }
    payload.update(overrides)
    return DocManifestEntry(**payload)


def test_load_docs_manifest_has_one_default_page() -> None:
    manifest = load_docs_manifest()

    defaults = [entry for entry in manifest if entry.default]
    assert len(defaults) == 1
    assert defaults[0].slug == "index"


def test_validate_manifest_rejects_duplicate_slugs(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Start Here\n", encoding="utf-8")

    entries = [
        _entry(),
        _entry(title="Duplicate", order=20, default=False),
    ]

    with pytest.raises(ValueError, match="Duplicate doc slug"):
        validate_manifest_entries(entries, docs_dir=docs_dir)


def test_validate_manifest_rejects_missing_markdown_files(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    with pytest.raises(ValueError, match="Missing markdown file"):
        validate_manifest_entries([_entry()], docs_dir=docs_dir)


def test_validate_manifest_rejects_multiple_defaults(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Start Here\n", encoding="utf-8")
    (docs_dir / "core-concepts.md").write_text("# Core Concepts\n", encoding="utf-8")

    entries = [
        _entry(),
        _entry(
            slug="core-concepts",
            title="Core Concepts",
            section="Reference",
            order=10,
            summary="Control plane, data plane, and hand-off.",
        ),
    ]

    with pytest.raises(ValueError, match="Exactly one doc entry must set default=true"):
        validate_manifest_entries(entries, docs_dir=docs_dir)


def test_validate_manifest_rejects_alias_collisions(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Overview\n", encoding="utf-8")
    (docs_dir / "quickstart.md").write_text("# Quickstart\n", encoding="utf-8")

    entries = [
        _entry(aliases=["old-overview"]),
        _entry(
            slug="quickstart",
            title="Quickstart",
            section="Get Started",
            order=20,
            summary="Fastest path into the product.",
            default=False,
            aliases=["old-overview"],
        ),
    ]

    with pytest.raises(ValueError, match="Duplicate doc alias"):
        validate_manifest_entries(entries, docs_dir=docs_dir)


def test_generated_outputs_match_checked_in_files() -> None:
    manifest = load_docs_manifest()

    assert render_sitemap_markdown(manifest) == (DOCS_DIR / "sitemap.md").read_text(encoding="utf-8")
    assert render_llms_txt(manifest) == LLMS_PATH.read_text(encoding="utf-8")


def test_manifest_json_matches_loaded_manifest() -> None:
    manifest_json = json.loads((DOCS_DIR / "_manifest.json").read_text(encoding="utf-8"))
    manifest = load_docs_manifest()

    assert [entry.model_dump() for entry in manifest] == manifest_json
