# Performance Protocol

SESSION_COUNT=2
MODES=P0,P1,P2
WARMUP_PER_MODE_PER_SESSION=200
MEASURED_PER_MODE_PER_SESSION=2000
BLOCK_SIZE=100
P0=policy-empty non-target write-mode open on frozen quiet H4 runtime.
P1=one active target rule, same non-target write-mode open as P0.
P2=one active target rule, protected target write-mode open, expected deny.
P1_MINUS_P0_NAME=incremental active-policy non-match cost
P2_NAME=matched deny-path app-visible latency
