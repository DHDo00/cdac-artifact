# V2 reset and carry-over oracle

_Byte/semantic inheritance from the independently validated closure package._

---

## 📋 Required pre-state

Every trial records immutable boot UUID, current arm hint, exact policy dump
and hash, all switch values, complete counter map and scopes, context/frame
balance, pop-fail state, descriptor acquire/release/outstanding accounting,
guest/host timestamps, and a log watermark. The snapshot is retained even if a
later pre-invocation step fails.

## 🔧 Reset sequence

1. Stop control-plane operations that can create measured state.
2. Clear runtime policy and set every registered switch to neutral (`N`).
3. Drain/clear guest log streams and establish a monotonic/kernel watermark.
4. Issue the existing `printf reset > /sys/kernel/debug/iguard/quiet_counters`.
5. Poll complete projections until two consecutive snapshots have the same
   frozen trial-sensitive projection, both are complete, and policy/switch/
   context/descriptor/pop-fail gates are clean. Timeout, missing field,
   unstable projection, or watermark failure is `RESET_FAIL` and hard-stops.
6. Retain both full raw snapshots and all timestamps. Compute trial values from
   immutable pre-state baseline/delta; broad module counters are not required
   to be zero.
7. Preserve aliases in `COUNTER_ALIAS_MAP.tsv`; aliases are not independent
   events. Verify policy, switches, frame/context, pop-fail, descriptor, and
   capability accounting before freezing the next arm.

## ✅ Completion conjuncts

- boot identity is unchanged;
- two complete stable projections are retained and identical;
- runtime policy is empty and all switches are neutral;
- trial-sensitive counters and unexpected pop-fail/mismatch state are zero;
- context and descriptor accounting are closed;
- watermark excludes late events and workload markers before invocation;
- any failed conjunct causes a hard stop, with no silent retry.

The validated closure root is
`cdac_rq4_carry_over_closure_20260807_010422`; its frozen root cause is
`MULTIPLE_CAUSES` (reset completion race, counter-scope mismatch, and
controller bookkeeping error), with `REAL_CARRY_OVER_CONFIRMED=no`. These are
engineering provenance facts, not V2 scientific results.
