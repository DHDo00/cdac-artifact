# Paper-Safe Results

On the frozen AOSP 16 Cuttlefish H4 runtime, activating one reviewed target-object rule changed the application-visible latency of the same non-matching DownloadProvider open by median block-paired delta 252025.250 ns (95% bootstrap CI [-183755.500, 925107.750] ns). Matched protected opens were rejected with pooled median app-visible latency 2437371.000 ns without target receiver-side descriptor installation or usable PFD return. The results were reproduced across two independently booted sessions.

Scope: application-visible open latency only. P0 is patched quiet H4 runtime, not pristine Android. P1-P0 is active-policy incremental non-match cost. P2 is matched deny latency. In-runtime decision latency was not measured. Cuttlefish absolute latency is not directly compared with Pixel 8/AOSP15 hardware results.
