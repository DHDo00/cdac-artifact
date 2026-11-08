# V2 frozen analysis plan

## 📊 Primary estimator

For each boot/block with five registered-success rows for A, B, and C, compute
the five-row medians and paired differences
`Delta_BA = median(B) - median(A)` and
`Delta_CB = median(C) - median(B)`. Report pooled and boot-specific medians
and 95% percentile intervals from 10,000 boot-stratified, whole-block
bootstrap replicates using `BOOTSTRAP_SEED_V2`.

## 📈 Secondary and denial summaries

`Delta_CA`, arm means/medians/P95/P99, and boot-specific distributions are
secondary. D reports only N, mean, P50, P95, and P99 for absolute
denial-response latency, pooled and by boot. No denial overhead or cross-arm D
contrast is computed.

The byte-frozen `04_analysis/ANALYSIS_SCRIPT.py` is the controlling estimator;
it reads only V2 scientific ledgers and validates protocol/schedule identity
before deriving any statistic.
