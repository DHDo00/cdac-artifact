#!/usr/bin/env bash
set -euo pipefail
SDK=Android/Sdk
BT=$SDK/build-tools/36.0.0
PLATFORM=$SDK/platforms/android-35/android.jar
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/build"
rm -rf "$OUT"; mkdir -p "$OUT/classes" "$OUT/dex"
"$BT/aapt2" link -o "$OUT/base.apk" --manifest "$HERE/AndroidManifest.xml" \
  -I "$PLATFORM" --min-sdk-version 35 --target-sdk-version 35 --version-code 2026102301 --version-name esp-timing-20261023
javac -source 1.8 -target 1.8 -bootclasspath "$PLATFORM" -d "$OUT/classes" \
  "$HERE/src/com/demo/esptiming/MainActivity.java"
"$BT/d8" --lib "$PLATFORM" --min-api 35 --output "$OUT/dex" $(find "$OUT/classes" -name '*.class')
cp "$OUT/dex/classes.dex" "$OUT/classes.dex"
(cd "$OUT" && zip -q -j base.apk classes.dex)
"$BT/zipalign" -f 4 "$OUT/base.apk" "$OUT/esp-timing-unsigned.apk"
if [ ! -f "$HERE/esptiming.keystore" ]; then
  keytool -genkeypair -keystore "$HERE/esptiming.keystore" -alias esptiming \
    -keyalg RSA -keysize 2048 -validity 3650 -storepass esptiming -keypass esptiming \
    -dname "CN=EspTiming, OU=CDAC, O=Lab, L=Shanghai, ST=Shanghai, C=CN"
fi
"$BT/apksigner" sign --ks "$HERE/esptiming.keystore" --ks-pass pass:esptiming \
  --key-pass pass:esptiming --out "$OUT/esp-timing-signed.apk" "$OUT/esp-timing-unsigned.apk"
"$BT/apksigner" verify --print-certs "$OUT/esp-timing-signed.apk" > "$OUT/verify.txt"
sha256sum "$OUT/esp-timing-signed.apk" > "$OUT/esp-timing-signed.apk.sha256"
echo "BUILT $OUT/esp-timing-signed.apk"
