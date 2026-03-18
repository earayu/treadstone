"""Export the OpenAPI spec from FastAPI app without starting the server.

Usage:
    python scripts/export_openapi.py              # writes openapi.json
    python scripts/export_openapi.py -o spec.json # custom output path
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from treadstone.main import app  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Export OpenAPI spec from FastAPI app")
    parser.add_argument("-o", "--output", default="openapi.json", help="Output file path (default: openapi.json)")
    args = parser.parse_args()

    spec = app.openapi()
    Path(args.output).write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
    print(f"OpenAPI spec exported to {args.output}")


if __name__ == "__main__":
    main()
