from __future__ import annotations

import argparse
from pathlib import Path

from treadstone.docs_manifest import LLMS_PATH, DOCS_DIR, load_docs_manifest, render_llms_txt, render_sitemap_markdown


def _check_output(path: Path, expected: str) -> None:
    actual = path.read_text(encoding="utf-8") if path.exists() else None
    if actual != expected:
        raise SystemExit(f"{path} is out of date. Run `uv run python scripts/generate_public_docs.py`.")


def _write_output(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    print(f"updated {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the public docs manifest and regenerate derived files.")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if generated files are out of date.")
    args = parser.parse_args()

    manifest = load_docs_manifest()
    outputs = {
        DOCS_DIR / "sitemap.md": render_sitemap_markdown(manifest),
        LLMS_PATH: render_llms_txt(manifest),
    }

    for path, content in outputs.items():
        if args.check:
            _check_output(path, content)
        else:
            _write_output(path, content)


if __name__ == "__main__":
    main()
