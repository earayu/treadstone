from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

SECTION_ORDER = (
    "Start Here",
    "Quickstarts",
    "Guides",
    "Reference",
    "Operations",
    "AI Docs",
)
LLMS_MIN_PRIORITY = 80

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = _REPO_ROOT / "web" / "public" / "docs"
DOCS_MANIFEST_PATH = DOCS_DIR / "_manifest.json"
LLMS_PATH = DOCS_DIR.parent / "llms.txt"


class DocManifestEntry(BaseModel):
    slug: str
    title: str
    section: str
    order: int = Field(ge=0)
    summary: str
    default: bool
    llm_priority: int = Field(ge=0)


def _missing_markdown_file(slug: str, docs_dir: Path) -> ValueError:
    return ValueError(f"Missing markdown file for slug '{slug}': {docs_dir / f'{slug}.md'}")


def validate_manifest_entries(
    entries: Iterable[DocManifestEntry],
    *,
    docs_dir: Path = DOCS_DIR,
) -> tuple[DocManifestEntry, ...]:
    manifest = list(entries)
    if not manifest:
        raise ValueError("Docs manifest must contain at least one page.")

    seen_slugs: set[str] = set()
    seen_orders: dict[str, set[int]] = defaultdict(set)
    default_count = 0

    for entry in manifest:
        if not _SLUG_PATTERN.fullmatch(entry.slug):
            raise ValueError(f"Invalid doc slug '{entry.slug}'. Use lowercase letters, numbers, and hyphens only.")
        if entry.slug in seen_slugs:
            raise ValueError(f"Duplicate doc slug '{entry.slug}' in docs manifest.")
        seen_slugs.add(entry.slug)

        if entry.section not in SECTION_ORDER:
            raise ValueError(
                f"Invalid docs section '{entry.section}' for slug '{entry.slug}'. "
                f"Allowed sections: {', '.join(SECTION_ORDER)}."
            )

        if entry.order in seen_orders[entry.section]:
            raise ValueError(
                f"Duplicate order {entry.order} in section '{entry.section}'. "
                "Each page must have a unique order within its section."
            )
        seen_orders[entry.section].add(entry.order)

        if not entry.summary.strip():
            raise ValueError(f"Doc summary for slug '{entry.slug}' must not be empty.")

        if entry.default:
            default_count += 1

        if not (docs_dir / f"{entry.slug}.md").exists():
            raise _missing_markdown_file(entry.slug, docs_dir)

    if default_count != 1:
        raise ValueError("Exactly one doc entry must set default=true.")

    return tuple(
        sorted(
            manifest,
            key=lambda entry: (SECTION_ORDER.index(entry.section), entry.order, entry.slug),
        )
    )


def load_docs_manifest(
    *,
    manifest_path: Path = DOCS_MANIFEST_PATH,
    docs_dir: Path | None = None,
) -> tuple[DocManifestEntry, ...]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = [DocManifestEntry.model_validate(item) for item in payload]
    return validate_manifest_entries(entries, docs_dir=docs_dir or manifest_path.parent)


@lru_cache(maxsize=1)
def get_docs_manifest() -> tuple[DocManifestEntry, ...]:
    return load_docs_manifest()


def clear_docs_manifest_cache() -> None:
    get_docs_manifest.cache_clear()


def get_default_doc(entries: Iterable[DocManifestEntry]) -> DocManifestEntry:
    for entry in entries:
        if entry.default:
            return entry
    raise ValueError("Docs manifest does not define a default page.")


def get_doc_slugs(entries: Iterable[DocManifestEntry] | None = None) -> set[str]:
    manifest = tuple(entries) if entries is not None else get_docs_manifest()
    return {entry.slug for entry in manifest}


def group_manifest_by_section(entries: Iterable[DocManifestEntry]) -> list[tuple[str, list[DocManifestEntry]]]:
    grouped: list[tuple[str, list[DocManifestEntry]]] = []
    manifest = list(entries)
    for section in SECTION_ORDER:
        items = [entry for entry in manifest if entry.section == section]
        if items:
            grouped.append((section, items))
    return grouped


def render_sitemap_markdown(entries: Iterable[DocManifestEntry]) -> str:
    manifest = list(entries)
    lines = [
        "# Treadstone Documentation Sitemap",
        "",
        "This file is generated from `/docs/_manifest.json`.",
        "Read [`/docs/index.md`](/docs/index.md) first if you are new.",
        "Read [`/docs/ai-index.md`](/docs/ai-index.md) first if you are an agent.",
        "",
    ]

    for section, items in group_manifest_by_section(manifest):
        lines.extend([f"## {section}", ""])
        for entry in items:
            lines.append(f"- [{entry.title}](/docs/{entry.slug}.md): {entry.summary}")
        lines.append("")

    lines.extend(
        [
            "## Public Endpoints",
            "",
            "- [`/docs/{slug}`](/docs/index): Returns raw Markdown when the client sends "
            "`Accept: text/markdown`; otherwise redirects to `/docs?page={slug}`.",
            "- [`/docs/sitemap.md`](/docs/sitemap.md): This complete documentation index.",
            "- [`/llms.txt`](/llms.txt): Short machine-oriented entrypoint.",
            "- [`/openapi.json`](/openapi.json): Generated OpenAPI document for the control plane.",
            "",
        ]
    )
    return "\n".join(lines)


def render_llms_txt(entries: Iterable[DocManifestEntry]) -> str:
    manifest = list(entries)
    important = [entry for entry in manifest if entry.llm_priority >= LLMS_MIN_PRIORITY]
    important.sort(key=lambda entry: (-entry.llm_priority, SECTION_ORDER.index(entry.section), entry.order, entry.slug))

    lines = [
        "# Treadstone",
        "",
        "> Agent-native sandbox platform for AI agents. Run code, control sandbox lifecycle, "
        "expose a data plane, and hand browser sessions to humans when the workflow demands it.",
        "",
        "## Primary Docs",
        "",
    ]

    for entry in important:
        lines.append(f"- [{entry.title}](/docs/{entry.slug}.md): {entry.summary}")

    lines.extend(
        [
            "",
            "## Task Map",
            "",
            "- Create a sandbox: [/docs/quickstart-agent-cli.md](/docs/quickstart-agent-cli.md), "
            "[/docs/quickstart-rest-api.md](/docs/quickstart-rest-api.md), "
            "[/docs/guide-sandboxes.md](/docs/guide-sandboxes.md)",
            "- Hand a browser to a human: [/docs/guide-browser-handoff.md](/docs/guide-browser-handoff.md), "
            "[/docs/ai-invariants.md](/docs/ai-invariants.md)",
            "- Use the proxy / data plane: [/docs/guide-data-plane-access.md](/docs/guide-data-plane-access.md), "
            "[/docs/api-reference.md](/docs/api-reference.md)",
            "- Understand auth and scope boundaries: [/docs/core-concepts.md](/docs/core-concepts.md), "
            "[/docs/api-reference.md](/docs/api-reference.md), "
            "[/docs/error-reference.md](/docs/error-reference.md)",
            "",
            "## Optional",
            "",
            "- [Documentation Sitemap](/docs/sitemap.md): Full hierarchical index",
            "- [GitHub](https://github.com/earayu/treadstone): Source, releases, and issues",
            "- [OpenAPI Spec](/openapi.json): Machine-readable control-plane API schema",
            "",
        ]
    )
    return "\n".join(lines)
