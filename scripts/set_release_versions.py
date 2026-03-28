from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


TOML_TARGETS = (
    ("pyproject.toml", "[project]"),
    ("cli/pyproject.toml", "[project]"),
    ("sdk/python/pyproject.toml", "[tool.poetry]"),
)

JSON_TARGETS = ("web/package.json",)
TS_TARGETS = ("web/src/lib/app-version.ts",)


def _update_version_in_section(content: str, section: str, version: str, file_label: str) -> str:
    section_pattern = re.compile(rf"(?ms)^({re.escape(section)}\n)(.*?)(?=^\[|\Z)")
    match = section_pattern.search(content)
    if match is None:
        raise ValueError(f"{file_label}: missing section {section}")

    body = match.group(2)
    updated_body, count = re.subn(r'(?m)^version = ".*"$', f'version = "{version}"', body, count=1)
    if count != 1:
        raise ValueError(f"{file_label}: missing version entry in {section}")

    return f"{content[:match.start(2)]}{updated_body}{content[match.end(2):]}"


def _update_package_json_version(content: str, version: str, file_label: str) -> str:
    updated, count = re.subn(
        r'(?m)^(\s*"version":\s*")[^"]+(",?)$',
        rf'\g<1>{version}\g<2>',
        content,
        count=1,
    )
    if count != 1:
        raise ValueError(f"{file_label}: missing package.json version entry")
    return updated


def _update_typescript_version_constant(content: str, version: str, file_label: str) -> str:
    updated, count = re.subn(
        r'(?m)^export const APP_VERSION = "[^"]+";$',
        f'export const APP_VERSION = "{version}";',
        content,
        count=1,
    )
    if count != 1:
        raise ValueError(f"{file_label}: missing APP_VERSION constant")
    return updated


def set_release_versions(root: Path, version: str) -> list[Path]:
    normalized_version = version.lstrip("v")
    updated_paths: list[Path] = []

    for relative_path, section in TOML_TARGETS:
        path = root / relative_path
        if not path.exists():
            raise FileNotFoundError(relative_path)

        content = path.read_text(encoding="utf-8")
        updated = _update_version_in_section(content, section, normalized_version, relative_path)
        path.write_text(updated, encoding="utf-8")
        updated_paths.append(path)

    for relative_path in JSON_TARGETS:
        path = root / relative_path
        if not path.exists():
            raise FileNotFoundError(relative_path)

        content = path.read_text(encoding="utf-8")
        updated = _update_package_json_version(content, normalized_version, relative_path)
        path.write_text(updated, encoding="utf-8")
        updated_paths.append(path)

    for relative_path in TS_TARGETS:
        path = root / relative_path
        if not path.exists():
            raise FileNotFoundError(relative_path)

        content = path.read_text(encoding="utf-8")
        updated = _update_typescript_version_constant(content, normalized_version, relative_path)
        path.write_text(updated, encoding="utf-8")
        updated_paths.append(path)

    return updated_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Set release versions across all publishable packages.")
    parser.add_argument("version", help="Release version, with or without the leading v.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to the current directory.")
    args = parser.parse_args()

    try:
        updated_paths = set_release_versions(Path(args.root).resolve(), args.version)
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1

    for path in updated_paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
