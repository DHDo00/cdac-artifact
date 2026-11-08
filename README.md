# CDAC

Cross-Domain Access Control for Android file re-delegation.

Prototype implementation and experiment data for the CDAC paper. The repo
contains source patches, small tools, and frozen experiment records. No build
images, no signing keys, no binaries.

## Layout

    code/android16/      framework and provider patches for AOSP 16
    code/android15/      minimal R1 port diffs for AOSP 15
    code/android17/      minimal R1 port diffs for AOSP 17
    code/kernel/         Linux 6.12.74 changes and new source files
    tools/               iguardctl_test, fixture APK sources, CVD scripts
    data/                frozen ledgers, protocols, and recompute scripts

Patch application order and build commands are in code/APPLY.md.

Each data/ subdirectory ships a SHA256SUMS.txt for the files in that
subdirectory. The checksums were generated for this redistribution copy.

## Data notes

- data/performance/  matched-build latency, SettingsProvider A/B/C, H4 DP,
  rule-count scaling, and concurrency attribution. Recompute with
  `bash recompute/run_all.sh` (Python 3 only for most steps; pandas and
  numpy are needed for the SettingsProvider step).
- data/mediaprovider/ MediaProvider openFile matrix replication, request and
  boot ledgers, schedule, and offline verification.
- data/platform-r1/  Android 15/16/17 R1 port boot records and per-request
  ledgers.
- data/policy/  policy accounting tables for the paper.
- data/esp-runtime/ and data/esp-exceptions/  ExternalStorageProvider
  enforcement and exception-input records.

## Fixtures

tools/fixtures holds the client app sources used by the workload. Run
`bash tools/fixtures/build_apks.sh` with the Android SDK build tools
(aapt2, d8, zipalign, apksigner) on PATH to rebuild the two test APKs.
A throwaway debug keystore is generated on first run.

## License

The framework and provider code derives from AOSP and keeps the Apache-2.0
headers of the original files. The kernel changes derive from the Linux
kernel (GPL-2.0-only). New files under code/ follow the license of the
directory they belong to. The experiment data is provided as-is.
