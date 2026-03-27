"""Update the image.tag in prod Helm values files to the given version."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HELM_VALUES_PATHS = [
    "deploy/treadstone/values-prod.yaml",
    "deploy/treadstone-web/values-prod.yaml",
]


def update_prod_image(root: Path, version: str) -> list[Path]:
    normalized = version.lstrip("v")
    updated_paths: list[Path] = []

    for rel_path in HELM_VALUES_PATHS:
        path = root / rel_path
        if not path.exists():
            raise FileNotFoundError(rel_path)

        content = path.read_text(encoding="utf-8")
        updated, count = re.subn(r"(?m)^(\s+tag:\s*)\S+$", rf"\g<1>{normalized}", content, count=1)
        if count != 1:
            raise ValueError(f"{rel_path}: missing image.tag entry")

        path.write_text(updated, encoding="utf-8")
        updated_paths.append(path)

    return updated_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Update prod Helm values image tags.")
    parser.add_argument("version", help="Release version, e.g. v0.4.2 or 0.4.2")
    parser.add_argument("--root", default=".", help="Repository root.")
    args = parser.parse_args()

    try:
        paths = update_prod_image(Path(args.root).resolve(), args.version)
        for p in paths:
            print(p)
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
