"""Export the OpenAPI spec from FastAPI app without starting the server.

Writes ``openapi.json`` (full spec, including admin and audit routes) and ``openapi-public.json``
(no ``/v1/admin`` or ``/v1/audit`` paths, for Python SDK generation).

Usage:
    python scripts/export_openapi.py              # writes openapi.json + openapi-public.json
    python scripts/export_openapi.py -o spec.json # custom path for full spec only
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# OpenAPI export should not depend on a developer having runtime secrets in the shell.
os.environ.setdefault("TREADSTONE_JWT_SECRET", "openapi_export_dummy_secret_value_1234567890")

from treadstone.main import app  # noqa: E402
from treadstone.openapi_spec import build_full_openapi_spec, filter_public_openapi  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Export OpenAPI spec from FastAPI app")
    parser.add_argument("-o", "--output", default="openapi.json", help="Output file path (default: openapi.json)")
    args = parser.parse_args()

    # Full spec for web / internal types (includes admin and audit routes).
    app.openapi_schema = None
    full_spec = build_full_openapi_spec(app)
    Path(args.output).write_text(json.dumps(full_spec, indent=2, ensure_ascii=False) + "\n")
    print(f"OpenAPI spec exported to {args.output}")

    public_path = Path("openapi-public.json")
    public_spec = filter_public_openapi(full_spec)
    public_path.write_text(json.dumps(public_spec, indent=2, ensure_ascii=False) + "\n")
    print(f"Public OpenAPI spec (no /v1/admin or /v1/audit) exported to {public_path}")


if __name__ == "__main__":
    main()
