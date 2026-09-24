"""Export the maintained runtime contract using its own dependency environment."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "deploy/sandbox-image/runtime/opt/treadstone/python"))


def main() -> None:
    from app.server import create_app

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    spec = create_app().openapi()
    spec["info"]["version"] = "1.0.0"
    path = ROOT / "scripts/sandbox_openapi_base.json"
    if args.check:
        assert json.loads(path.read_text()) == spec, "Regenerate the sandbox OpenAPI snapshot"
    else:
        path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
