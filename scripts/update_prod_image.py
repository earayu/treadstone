"""Update the image.tag in deploy/treadstone/values-prod.yaml to the given version."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HELM_VALUES_PATH = "deploy/treadstone/values-prod.yaml"


def update_prod_image(root: Path, version: str) -> Path:
    normalized = version.lstrip("v")
    path = root / HELM_VALUES_PATH
    if not path.exists():
        raise FileNotFoundError(HELM_VALUES_PATH)

    content = path.read_text(encoding="utf-8")
    updated, count = re.subn(r"(?m)^(\s+tag:\s*)\S+$", rf"\g<1>{normalized}", content, count=1)
    if count != 1:
        raise ValueError(f"{HELM_VALUES_PATH}: missing image.tag entry")

    path.write_text(updated, encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Update prod Helm values image tag.")
    parser.add_argument("version", help="Release version, e.g. v0.4.2 or 0.4.2")
    parser.add_argument("--root", default=".", help="Repository root.")
    args = parser.parse_args()

    try:
        path = update_prod_image(Path(args.root).resolve(), args.version)
        print(path)
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
