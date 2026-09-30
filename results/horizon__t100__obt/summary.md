## Loss from lies ($, cost minus honest-S_main cost on the same seed)

| Scenario | obt |
|---|---|
| 1_honest | 0.0 |
| 2_always_lie | 499.8 |
| 3_farm_then_lie | 60.6 |
| 4_slow_drift | 468.7 |
| 5_price_bait | 331.2 |
| 6_vague | 385.2 |
| 7_far_deadlines | 385.2 |
| 8_claim_splitting | 376.8 |
| 9_noisy_honest | 161.7 |
| 10_farm_fail_refarm | 51.8 |
| 11_extraction_attack | 384.7 |
| 12_sybil_reentry | 499.8 |

## Loss decomposition and bound (DESIGN §6)

loss_from_lies = damage + reroute_cost_diff + resid, every term relative to the honest run with the same defense and seed. damage: cost vs the same decisions with every relied-on promise kept; the bound Σ L_e applies to it (OBT only). reroute premium diff (reroute_cost_diff): extra backup premium on quantity rerouted after OVER_BUDGET/OVER_CLAIM blocks, vs the honest run. resid: everything else (other blocks, trajectory differences), reported as is.

| Scenario | Defense | loss_from_lies | damage | Σ bound | bound ok | reroute premium diff | resid | failure events |
|---|---|---|---|---|---|---|---|---|
| 1_honest | obt | 0.0 | 0.0 | 0.0 | yes | 0.0 | 0.0 | 0.0 |
| 2_always_lie | obt | 499.8 | 158.5 | 462.0 | yes | 66.0 | 275.3 | 33.0 |
| 3_farm_then_lie | obt | 60.6 | 45.0 | 70.0 | yes | 81.1 | -65.5 | 0.3 |
| 4_slow_drift | obt | 468.7 | 142.2 | 406.0 | yes | 62.3 | 264.2 | 29.0 |
| 5_price_bait | obt | 331.2 | 0.0 | 0.0 | yes | 10.0 | 321.2 | 0.0 |
| 6_vague | obt | 385.2 | 0.0 | 0.0 | yes | -20.0 | 405.2 | 0.0 |
| 7_far_deadlines | obt | 385.2 | 0.0 | 0.0 | yes | -20.0 | 405.2 | 0.0 |
| 8_claim_splitting | obt | 376.8 | 0.0 | 0.0 | yes | -13.3 | 390.2 | 0.0 |
| 9_noisy_honest | obt | 161.7 | -125.2 | 1,120.3 | yes | 20.7 | 266.2 | 4.7 |
| 10_farm_fail_refarm | obt | 51.8 | 24.3 | 65.3 | yes | 225.4 | -197.9 | 0.3 |
| 11_extraction_attack | obt | 384.7 | 0.0 | 0.0 | yes | -20.0 | 404.7 | 0.0 |
| 12_sybil_reentry | obt | 499.8 | 158.5 | 462.0 | yes | 66.0 | 275.3 | 33.0 |

## Reroute premium (honest S_main)

Absolute backup premium the defense's own reroutes cost in the honest scenario (not differenced).

| Defense | Reroute premium ($) |
|---|---|
| obt | 20.0 |

## Utility (scenarios 1 and 9)

| Scenario | Defense | Cost | Extra vs none | Blocked S_main orders |
|---|---|---|---|---|
| 1_honest | obt | 12,163.5 | - | 1.33 |
| 9_noisy_honest | obt | 12,325.2 | - | 5.0 |

## Overhead per round

| Defense | Tokens | Latency (s) | Added tokens vs none | Added latency vs none |
|---|---|---|---|---|
| obt | 187.91 | 1.22 | - | - |
