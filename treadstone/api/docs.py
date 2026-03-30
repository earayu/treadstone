"""
Documentation content-negotiation endpoint.

When a client sends `Accept: text/markdown`, returns raw Markdown for the requested
doc slug. Otherwise, redirects to the frontend SPA at `/docs?page={slug}`.

This enables AI agents and crawlers to fetch clean Markdown without any HTML noise:

    curl https://api.treadstone-ai.dev/docs/getting-started -H "Accept: text/markdown"
"""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["docs"])

# Docs directory: configurable via env var, falls back to web/public/docs
# relative to the working directory (repo root when running make dev-api).
_DEFAULT_DOCS_DIR = Path("web/public/docs")
_DOCS_DIR = Path(os.environ.get("TREADSTONE_DOCS_DIR", _DEFAULT_DOCS_DIR))

_KNOWN_SLUGS = {
    "getting-started",
    "cli-reference",
    "sdk-reference",
    "api-reference",
    "self-hosting",
    "sitemap",
}

_FRONTEND_DOCS_BASE = "/docs"


def _accepts_markdown(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/markdown" in accept


def _read_doc(slug: str) -> str | None:
    """Read a doc file. Returns None if not found. Guards against path traversal."""
    safe_slug = Path(slug).name  # strip any directory components
    doc_path = _DOCS_DIR / f"{safe_slug}.md"
    if not doc_path.exists():
        return None
    return doc_path.read_text(encoding="utf-8")


@router.get("/docs/sitemap.md")
async def docs_sitemap_md(request: Request) -> PlainTextResponse:
    """Serve the documentation sitemap as Markdown."""
    content = _read_doc("sitemap")
    if content is None:
        return PlainTextResponse("# Treadstone Documentation\n\nSitemap not found.", status_code=404)
    return PlainTextResponse(
        content,
        media_type="text/markdown; charset=utf-8",
        headers={"Vary": "Accept"},
    )


@router.get("/docs/{slug}")
async def docs_page(slug: str, request: Request):
    """
    Content-negotiation endpoint for documentation pages.

    - `Accept: text/markdown` → returns raw Markdown (200)
    - Other clients → redirects to the SPA docs page (302)
    """
    if slug not in _KNOWN_SLUGS:
        if _accepts_markdown(request):
            return PlainTextResponse(
                f"# Not Found\n\nDocument `{slug}` does not exist.",
                status_code=404,
                media_type="text/markdown; charset=utf-8",
            )
        return RedirectResponse(url=_FRONTEND_DOCS_BASE, status_code=302)

    if _accepts_markdown(request):
        content = _read_doc(slug)
        if content is None:
            logger.warning("Doc file missing for slug=%s (docs_dir=%s)", slug, _DOCS_DIR)
            return PlainTextResponse(
                f"# Not Found\n\nDocument `{slug}` is not available.",
                status_code=404,
                media_type="text/markdown; charset=utf-8",
            )
        return PlainTextResponse(
            content,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Vary": "Accept",
                "Cache-Control": "public, max-age=300",
            },
        )

    return RedirectResponse(
        url=f"{_FRONTEND_DOCS_BASE}?page={slug}",
        status_code=302,
    )
