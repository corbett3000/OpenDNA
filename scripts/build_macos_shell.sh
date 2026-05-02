#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="OpenDNA"
PRODUCT_DIR="$ROOT_DIR/build/macos/${APP_NAME}.app"
CONTENTS_DIR="$PRODUCT_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
SOURCE_DIR="$ROOT_DIR/macos/OpenDNAShell/Sources/OpenDNAShell"
PLIST_PATH="$ROOT_DIR/macos/OpenDNAShell/Support/Info.plist"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "error: missing Swift shell sources at $SOURCE_DIR" >&2
  exit 1
fi

if [[ ! -f "$ROOT_DIR/.venv/bin/python3" ]]; then
  echo "error: missing repo virtualenv at $ROOT_DIR/.venv" >&2
  echo "Create it first with: python3 -m venv .venv && source .venv/bin/activate && pip install -e \".[dev,all]\"" >&2
  exit 1
fi

SDK_PATH="$(xcrun --sdk macosx --show-sdk-path)"
ARCH="$(uname -m)"
TARGET="${ARCH}-apple-macos13.0"

rm -rf "$PRODUCT_DIR"
mkdir -p "$MACOS_DIR"
cp "$PLIST_PATH" "$CONTENTS_DIR/Info.plist"
printf 'APPL????' > "$CONTENTS_DIR/PkgInfo"

SWIFT_SOURCES=()
while IFS= read -r source; do
  SWIFT_SOURCES+=("$source")
done < <(find "$SOURCE_DIR" -name '*.swift' | sort)

xcrun swiftc \
  -sdk "$SDK_PATH" \
  -target "$TARGET" \
  -parse-as-library \
  -framework SwiftUI \
  -framework WebKit \
  -framework AppKit \
  "${SWIFT_SOURCES[@]}" \
  -o "$MACOS_DIR/$APP_NAME"

codesign --force --deep --sign - "$PRODUCT_DIR" >/dev/null 2>&1 || true

echo "Built $PRODUCT_DIR"

if [[ "${1:-}" == "--open" ]]; then
  open "$PRODUCT_DIR"
fi
