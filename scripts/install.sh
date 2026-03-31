#!/bin/sh
# Treadstone CLI installer for macOS and Linux
# Usage:
#   curl -fsSL https://treadstone-ai.dev/install.sh | sh
#   curl -fsSL https://github.com/earayu/treadstone/releases/latest/download/install.sh | sh
#
# Environment variables:
#   TREADSTONE_VERSION     Override version (e.g. "v0.1.4"). Default: latest release.
#   TREADSTONE_INSTALL_DIR Override install directory. Default: /usr/local/bin (falls back to ~/.local/bin).

set -e

REPO="earayu/treadstone"
BINARY_NAME="treadstone"

# ── Platform detection ───────────────────────────────────────────────────────

OS=$(uname -s)
ARCH=$(uname -m)

case "$OS" in
  Darwin)
    case "$ARCH" in
      arm64)           ARTIFACT="treadstone-darwin-arm64" ;;
      x86_64)          ARTIFACT="treadstone-darwin-amd64" ;;
      *)               echo "Unsupported architecture: $ARCH" >&2; exit 1 ;;
    esac
    ;;
  Linux)
    case "$ARCH" in
      x86_64 | amd64)  ARTIFACT="treadstone-linux-amd64" ;;
      *)               echo "Unsupported architecture: $ARCH" >&2; exit 1 ;;
    esac
    ;;
  *)
    echo "Unsupported OS: $OS" >&2
    echo "For Windows, run in PowerShell:" >&2
    echo "  irm https://treadstone-ai.dev/install.ps1 | iex" >&2
    exit 1
    ;;
esac

# ── Resolve download URL ─────────────────────────────────────────────────────

VERSION="${TREADSTONE_VERSION:-latest}"

if [ "$VERSION" = "latest" ]; then
  BASE_URL="https://github.com/$REPO/releases/latest/download"
else
  BASE_URL="https://github.com/$REPO/releases/download/$VERSION"
fi

# ── Resolve install dir ──────────────────────────────────────────────────────

if [ -n "$TREADSTONE_INSTALL_DIR" ]; then
  INSTALL_DIR="$TREADSTONE_INSTALL_DIR"
elif [ -w "/usr/local/bin" ]; then
  INSTALL_DIR="/usr/local/bin"
else
  INSTALL_DIR="$HOME/.local/bin"
  mkdir -p "$INSTALL_DIR"
fi

INSTALL_PATH="$INSTALL_DIR/$BINARY_NAME"

# ── Download ─────────────────────────────────────────────────────────────────

echo "Downloading $ARTIFACT from $BASE_URL ..."
curl -fsSL "$BASE_URL/$ARTIFACT" -o "$INSTALL_PATH"
chmod +x "$INSTALL_PATH"

# ── Checksum verification (best-effort) ──────────────────────────────────────

TMP_CHECKSUMS=$(mktemp)
if curl -fsSL "$BASE_URL/checksums.txt" -o "$TMP_CHECKSUMS" 2>/dev/null; then
  EXPECTED=$(grep "$ARTIFACT" "$TMP_CHECKSUMS" | awk '{print $1}')
  if [ -n "$EXPECTED" ]; then
    if command -v sha256sum >/dev/null 2>&1; then
      ACTUAL=$(sha256sum "$INSTALL_PATH" | awk '{print $1}')
    elif command -v shasum >/dev/null 2>&1; then
      ACTUAL=$(shasum -a 256 "$INSTALL_PATH" | awk '{print $1}')
    else
      ACTUAL=""
    fi

    if [ -n "$ACTUAL" ]; then
      if [ "$EXPECTED" = "$ACTUAL" ]; then
        echo "Checksum verified."
      else
        echo "Checksum mismatch! Removing download." >&2
        rm -f "$INSTALL_PATH"
        rm -f "$TMP_CHECKSUMS"
        exit 1
      fi
    fi
  fi
fi
rm -f "$TMP_CHECKSUMS"

# ── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo "treadstone installed to $INSTALL_PATH"

if ! echo ":$PATH:" | grep -q ":$INSTALL_DIR:"; then
  echo ""
  echo "NOTE: $INSTALL_DIR is not in your PATH. Add the following to your shell profile:"
  echo "  export PATH=\"\$PATH:$INSTALL_DIR\""
fi

echo ""
echo "Run: treadstone --help"
