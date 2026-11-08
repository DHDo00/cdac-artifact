# Final paper eligibility

PAPER_ALLOW_PATH_SLOT=FILLABLE
PAPER_DENIAL_LATENCY_SLOT=FILLABLE
NATIVE_ANDROID_OVERHEAD_SLOT=NOT_EVALUATED
DENIAL_OVERHEAD_SLOT=NOT_EVALUATED
UNIVERSAL_LOW_OVERHEAD_SLOT=NOT_EVALUATED

Eligible wording is limited to the same-artifact CDAC-inactive baseline, incremental latency of entering the active CDAC path, incremental latency of one registered nonmatching lookup, absolute denial-response latency, and a two-boot result on one retained S10 artifact.
The registered verbose-audit verification instrumentation was active for every invocation; results therefore describe this retained, instrumented route and are not a kernel-only cost.
