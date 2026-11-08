# Final numeric summary

Protocol SHA-256: `d5913d0e448a84dcb8af10f68a764f1a5805845b612773820f01753c34625685`.
Raw measured denominator: A=500, B=500, C=500, D=500; total=2000.
Registered-success rows: A=500, B=500, C=500, D=500.
Complete paired A/B/C blocks: boot_1=50, boot_2=50, pooled=100.

## Primary paired allow-path contrasts

- Delta_BA: pooled median 1924708.500 ns (1924.708 µs); 95% stratified block-bootstrap interval [1396098.000, 2707998.000] ns ([1396.098, 2707.998] µs).
- Delta_CB: pooled median -200872.000 ns (-200.872 µs); 95% stratified block-bootstrap interval [-730023.425, 361999.000] ns ([-730.023, 361.999] µs).

Boot-specific medians:

- boot_1 Delta_BA: 1885436.500 ns (1885.437 µs), complete blocks=50.
- boot_1 Delta_CB: -748303.500 ns (-748.303 µs), complete blocks=50.
- boot_2 Delta_BA: 2149506.000 ns (2149.506 µs), complete blocks=50.
- boot_2 Delta_CB: 193187.500 ns (193.188 µs), complete blocks=50.

## Secondary allow-path contrast

- Delta_CA: pooled median 1726082.000 ns (1726.082 µs); 95% interval [1081608.500, 2437742.000] ns.

## Absolute denial-response latency

- Pooled registered denial N=500 (raw D denominator=500).
- Mean=13743390.910 ns (13743.391 µs).
- P50=14165936.500 ns (14165.936 µs).
- P95=18446476.150 ns (18446.476 µs).
- P99=21078017.990 ns (21078.018 µs).

D is an absolute latency distribution. No D-A, D-B, D-C, percentage overhead, native-denial overhead, or kernel-only cost was computed.
