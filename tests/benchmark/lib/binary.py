"""Manage the treadstone CLI binary for benchmark runs.

Priority (highest to lowest):
  1. --binary CLI flag  → use as-is, skip install
  2. TREADSTONE_BINARY env var → use as-is, skip install
  3. .bin/treadstone already installed with matching version → reuse
  4. Download via the official install script: https://treadstone-ai.dev/install.sh
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Default install dir inside the benchmark tree (gitignored)
_BIN_DIR = Path(__file__).parent.parent / ".bin"
_BINARY_NAME = "treadstone"


def resolve(version: str = "latest", binary_override: str | None = None) -> Path:
    """Return the path to a ready-to-use treadstone binary.

    Args:
        version: "latest" or a specific version string like "0.8.8".
        binary_override: If set, use this path directly without any checks.

    Returns:
        Path to the binary.

    Raises:
        SystemExit: If the binary cannot be resolved or installed.
    """
    # 1. Explicit override via argument or env var
    override = binary_override or os.environ.get("TREADSTONE_BINARY")
    if override:
        p = Path(override)
        if not p.exists():
            print(f"Error: TREADSTONE_BINARY '{override}' does not exist.", file=sys.stderr)
            sys.exit(1)
        _print_version(p)
        return p

    # 2. Already installed in .bin/ with correct version
    candidate = _BIN_DIR / _BINARY_NAME
    if candidate.exists():
        installed_version = _get_version(candidate)
        if version == "latest" or installed_version == version:
            print(f"Using cached binary: {candidate} (version {installed_version})")
            return candidate
        else:
            print(f"Cached binary version {installed_version!r} != requested {version!r}; reinstalling.")

    # 3. Download via official install script
    return _install(version)


def _install(version: str) -> Path:
    """Run the official install.sh script into .bin/."""
    _BIN_DIR.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["TREADSTONE_INSTALL_DIR"] = str(_BIN_DIR)
    if version != "latest":
        env["TREADSTONE_VERSION"] = f"v{version}"

    print(f"Installing treadstone binary (version={version}) into {_BIN_DIR} ...")
    result = subprocess.run(
        "curl -fsSL https://treadstone-ai.dev/install.sh | sh",
        shell=True,
        env=env,
    )
    if result.returncode != 0:
        print("Error: install.sh failed. Check your network connection.", file=sys.stderr)
        sys.exit(1)

    binary = _BIN_DIR / _BINARY_NAME
    if not binary.exists():
        print(f"Error: binary not found at {binary} after install.", file=sys.stderr)
        sys.exit(1)

    _print_version(binary)
    return binary


def _get_version(binary: Path) -> str:
    """Return the version string reported by the binary, or 'unknown'."""
    try:
        result = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # treadstone --version typically prints "treadstone x.y.z"
        output = (result.stdout or result.stderr).strip()
        parts = output.split()
        return parts[-1] if parts else "unknown"
    except Exception:
        return "unknown"


def _print_version(binary: Path) -> None:
    version = _get_version(binary)
    print(f"treadstone binary: {binary} (version {version})")
