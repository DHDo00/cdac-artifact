# V2 exclusions and stopping rules

## 📋 Pre-invocation exclusions

Only host/CVD/ADB failure before broadcast, artifact mismatch before
invocation, missing frozen timestamp field before invocation, no workload
invocation, wrong-arm state before invocation, or inability to form a complete
row before invocation contributes zero scientific rows. Such recovery is
logged and cannot alter the schedule.

## 🔒 Post-invocation retention

Once the invocation sentinel or broadcast begins, the row is permanent in the
raw denominator. Failures, timeouts, abnormal outcomes, slow/fast values,
oracle failures, and cleanup failures are retained and classified. No trim,
winsorization, outlier deletion, replacement, or rerun is allowed.

## 🛑 Hard stops

Stop for artifact/protocol/hash mismatch, failed V2 reset/carry-over oracle,
verified state contamination, wrong binary/controller/parser, systematic
parser corruption, unresolvable CVD/ADB failure, or safety/integrity risk.
Never stop or adapt for contrast direction, interval position, significance,
boot speed, heavy tails, or denial latency magnitude.
