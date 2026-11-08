# Reset procedure V2 candidate

This is an engineering candidate, not a frozen protocol. It preserves the V1 carry-over oracle and changes only the observation/reset boundary:

1. Record an immutable pre-state snapshot containing boot UUID, arm, rule/policy dump hash, all switches, counter map, context/frame balance, pop-fail state, and descriptor acquire/release/outstanding state.
2. Stop issuing workload or control-plane operations that can create the measured state; clear the runtime policy and set all switches to their neutral values.
3. Drain/flush the controller and guest log streams and record a monotonic log watermark. No event with a sequence/timestamp at or before the trial boundary may remain unclassified.
4. Issue the existing `printf reset > /sys/kernel/debug/iguard/quiet_counters` operation. This does not modify the retained artifact.
5. Poll the counter file until two consecutive complete snapshots have an identical frozen trial-sensitive projection (or until a frozen timeout); retain both full raw snapshots and timestamps. Module/control-plane counters remain in the raw snapshots and may advance during this wait. A missing field, projection instability, or timeout is a hard stop.
6. Compute trial values as post-minus-immutable-pre deltas for counters whose scope permits it. Treat control-plane/module cumulative counters as scoped accounting diagnostics, not trial-local zeroes. Preserve aliases as aliases and never count an alias as an independent event.
7. Verify policy empty, switches neutral, context stack/frame empty, pop-fail accounting consumed according to arm, descriptor accounting balanced, and no residual rule/context state.
8. Freeze the next arm state only after every completion oracle is true. Any failed conjunct stops the run and retains the row; it never silently retries.

The procedure is acceptable for V2 only if the independent reset-only and arm-transition probes below pass and the global Cuttlefish state is restored after probing.
