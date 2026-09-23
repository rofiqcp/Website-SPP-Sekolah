#!/bin/bash
set -euo pipefail
OUT="${1:-android/app/debug.keystore}"
CN="El Yaomy SPP"
OU="Development"
O="El Yaomy"
L="Klaten"
ST="Central Java"
C="ID"
PASS="android"

mkdir -p "$(dirname "$OUT")"
keytool -genkeypair -v \
  -keystore "$OUT" \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -alias androiddebugkey \
  -storepass "$PASS" -keypass "$PASS" \
  -dname "CN=$CN, OU=$OU, O=$O, L=$L, ST=$ST, C=$C"
echo "Keystore: $OUT"
