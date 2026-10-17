#!/usr/bin/env bash
# Release build: clean build with only sdkconfig.defaults (no dev options),
# merged flash image for `esptool write-flash 0x0`, ESP Web Tools manifest,
# and a ready-to-host flasher site.
#
# Usage: scripts/release.sh
# Output:
#   dist/esp32-ctf-v<VERSION>.bin     merged image (bootloader + partition table + app)
#   dist/manifest.json                ESP Web Tools manifest
#   web/flasher/dist-site/            index.html + manifest.json + .bin (static site)
set -euo pipefail

VERSION="0.1.0"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="$ROOT/build-release"
DIST="$ROOT/dist"
SITE="$ROOT/web/flasher/dist-site"
BIN_NAME="esp32-ctf-v${VERSION}.bin"

# ESP-IDF environment (skip if already exported in this shell).
if ! command -v idf.py >/dev/null 2>&1; then
    IDF_DIR="${IDF_PATH:-$HOME/esp/esp-idf}"
    if [ ! -f "$IDF_DIR/export.sh" ]; then
        echo "error: ESP-IDF not found (set IDF_PATH or install to ~/esp/esp-idf)" >&2
        exit 1
    fi
    # shellcheck disable=SC1091
    . "$IDF_DIR/export.sh" >/dev/null
fi

cd "$ROOT"

# Clean build. SDKCONFIG points inside the build dir so a developer's root
# `sdkconfig` (which may have dev options) is never used; defaults come only
# from sdkconfig.defaults, never from a sdkconfig.*.local overlay.
rm -rf "$BUILD"
idf.py -B "$BUILD" \
    -DSDKCONFIG="$BUILD/sdkconfig" \
    -DSDKCONFIG_DEFAULTS="$ROOT/sdkconfig.defaults" \
    build

# Refuse to ship a build with any dev option enabled.
if grep -E '^CONFIG_CTF_[A-Z0-9_]*(DEV|DEV_STA|SIZE_PROBE)[A-Z0-9_]*=y' "$BUILD/sdkconfig"; then
    echo "error: dev option enabled in release sdkconfig (see above)" >&2
    exit 1
fi

mkdir -p "$DIST"
rm -f "$DIST/$BIN_NAME" "$DIST/manifest.json"

# flash_args lists flash mode/freq/size plus every offset/file pair, with
# paths relative to the build dir.
(cd "$BUILD" && esptool --chip esp32 merge-bin -o "$DIST/$BIN_NAME" @flash_args)

cat > "$DIST/manifest.json" <<EOF
{
  "name": "ESP32 Multi-Track CTF",
  "version": "${VERSION}",
  "new_install_prompt_erase": true,
  "builds": [
    {
      "chipFamily": "ESP32",
      "parts": [
        { "path": "${BIN_NAME}", "offset": 0 }
      ]
    }
  ]
}
EOF

rm -rf "$SITE"
mkdir -p "$SITE"
cp "$ROOT/web/flasher/index.html" "$SITE/index.html"
cp "$DIST/manifest.json" "$SITE/manifest.json"
cp "$DIST/$BIN_NAME" "$SITE/$BIN_NAME"

SIZE=$(stat -c %s "$DIST/$BIN_NAME")
echo
echo "Release v${VERSION}"
echo "  image:    dist/$BIN_NAME ($SIZE bytes)"
echo "  sha256:   $(sha256sum "$DIST/$BIN_NAME" | cut -d' ' -f1)"
echo "  manifest: dist/manifest.json"
echo "  site:     web/flasher/dist-site/ (host as static files)"
echo "  flash:    esptool --chip esp32 -p <PORT> write-flash 0x0 dist/$BIN_NAME"
