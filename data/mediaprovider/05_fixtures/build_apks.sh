#!/usr/bin/env bash
set -euo pipefail
SDK=Android/Sdk
BT=$SDK/build-tools/35.0.1
PLATFORM=$SDK/platforms/android-35/android.jar
HERE="$(cd "$(dirname "$0")" && pwd)"
build_one() {
  local app=$1
  local OUT="$HERE/$app/build"
  rm -rf "$OUT"; mkdir -p "$OUT/classes" "$OUT/dex"
  local assets_opt=()
  if [ -d "$HERE/$app/assets" ]; then assets_opt=(-A "$HERE/$app/assets"); fi
  "$BT/aapt2" link -o "$OUT/base.apk" --manifest "$HERE/$app/AndroidManifest.xml" \
    -I "$PLATFORM" --min-sdk-version 24 --target-sdk-version 35 --version-code 1 --version-name 1.0 \
    "${assets_opt[@]}"
  javac -source 1.8 -target 1.8 -bootclasspath "$PLATFORM" -d "$OUT/classes" \
    $(find "$HERE/$app/src" -name '*.java')
  "$BT/d8" --lib "$PLATFORM" --min-api 24 --output "$OUT/dex" $(find "$OUT/classes" -name '*.class')
  cp "$OUT/dex/classes.dex" "$OUT/classes.dex"
  (cd "$OUT" && zip -q -j base.apk classes.dex)
  "$BT/zipalign" -f 4 "$OUT/base.apk" "$OUT/$app-unsigned.apk"
  "$BT/apksigner" sign --ks "$HERE/espafdtest.keystore" --ks-pass pass:espafdtest \
    --key-pass pass:espafdtest --out "$OUT/$app-signed.apk" "$OUT/$app-unsigned.apk"
  sha256sum "$OUT/$app-signed.apk" > "$OUT/$app-signed.apk.sha256"
  echo "BUILT $OUT/$app-signed.apk"
}
build_one app_a
build_one app_b
