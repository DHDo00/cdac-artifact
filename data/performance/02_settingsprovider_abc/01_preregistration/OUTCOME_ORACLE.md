# V2 outcome oracle

## 📋 Common identity conjuncts

Every row carries the V2 protocol hash, boot artifact manifest, route tuple,
caller/workload identity, object-selection identity, complete APK timing field,
reset completion result, exact arm/rule state, cleanup result, and watermark
audit. After the invocation sentinel, the row is retained regardless of oracle
success.

## 🧪 A/B/C allow path

- A: registered bypass markers, no target decision/apply/enforce, success, and
  returned/installed/usable capability.
- B: active target decision, empty policy, `matched=0`, `rule_src=default`,
  allow apply, success, and usable capability.
- C: exactly one legal decoy rule, distinct target object, active decision,
  nonmatching lookup (`matched=0`, `rule_src=default`), success, and usable
  capability.

All A/B/C rows additionally require V2 reset completion, route hit, complete
latency, and balanced cleanup.

## 🛡️ D denial

D requires exact reviewed target match (`matched=1`, `rule_src=runtime`), direct
`errno=-13`/`verdict=deny-now`, registered app EACCES, no capability or
descriptor, and balanced denied acquire/release accounting with zero
outstanding/install count. D is reported only as absolute denial-response
latency.
