#!/bin/bash
#
# Copy APK hasil build ke backend/static/download dengan format spp-elyaomy-{version}.apk
# Usage: ./copy-apk.sh <path-to-apk> <version>
# Example: ./copy-apk.sh ~/android-build/app-release.apk 1.2.0
#

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

if [ $# -lt 2 ]; then
    echo -e "${YELLOW}Usage:${NC} $0 <apk-file> <version>"
    echo -e "${CYAN}Example:${NC} $0 ~/build/app-release.apk 1.2.0"
    exit 1
fi

APK_SOURCE="$1"
VERSION="$2"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOWNLOAD_DIR="$SCRIPT_DIR/backend/static/download"

if [ ! -f "$APK_SOURCE" ]; then
    echo -e "${RED}Error:${NC} APK file tidak ditemukan: $APK_SOURCE"
    exit 1
fi

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${RED}Error:${NC} Format version harus X.Y.Z (contoh: 1.2.0)"
    exit 1
fi

if ! [[ "$APK_SOURCE" =~ \.apk$ ]]; then
    echo -e "${RED}Error:${NC} File harus berekstensi .apk"
    exit 1
fi

mkdir -p "$DOWNLOAD_DIR"

TARGET_NAME="spp-elyaomy-${VERSION}.apk"
TARGET_PATH="$DOWNLOAD_DIR/$TARGET_NAME"

APK_SIZE=$(stat -f%z "$APK_SOURCE" 2>/dev/null || stat -c%s "$APK_SOURCE" 2>/dev/null)
APK_SIZE_MB=$((APK_SIZE / 1024 / 1024))

echo ""
echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║        Copy APK ke Download Folder     ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "   Source:  ${YELLOW}$APK_SOURCE${NC}"
echo -e "   Version: ${GREEN}$VERSION${NC}"
echo -e "   Size:    ${CYAN}${APK_SIZE_MB}MB${NC}"
echo -e "   Target:  ${YELLOW}$TARGET_PATH${NC}"
echo ""

if [ -f "$TARGET_PATH" ]; then
    echo -e "${YELLOW}⚠  File sudah ada. Overwrite?${NC} [y/N] "
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo -e "${RED}Dibatalkan${NC}"
        exit 1
    fi
fi

cp "$APK_SOURCE" "$TARGET_PATH"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ APK berhasil dicopy${NC}"
    echo ""
    echo -e "Download URL: ${CYAN}/api/apk/download/$TARGET_NAME${NC}"
    echo -e "Latest endpoint akan otomatis serve file ini jika paling baru."
    echo ""
else
    echo -e "${RED}✗ Error saat copy file${NC}"
    exit 1
fi
