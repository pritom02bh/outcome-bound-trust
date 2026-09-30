## Loss from lies ($, cost minus honest-S_main cost on the same seed)

| Scenario | reputation |
|---|---|
| 1_honest | 0.0 |
| 2_always_lie | 1,367.3 |
| 3_farm_then_lie | 55.7 |
| 4_slow_drift | 861.0 |
| 5_price_bait | 2,725.5 |
| 6_vague | 1,093.8 |
| 7_far_deadlines | 1,356.2 |
| 8_claim_splitting | 1,377.0 |
| 9_noisy_honest | 560.5 |
| 10_farm_fail_refarm | 132.1 |
| 11_extraction_attack | 1,127.2 |
| 12_sybil_reentry | 2,217.5 |

## Loss decomposition and bound (DESIGN §6)

loss_from_lies = damage + reroute_cost_diff + resid, every term relative to the honest run with the same defense and seed. damage: cost vs the same decisions with every relied-on promise kept; the bound Σ L_e applies to it (OBT only). reroute premium diff (reroute_cost_diff): extra backup premium on quantity rerouted after OVER_BUDGET/OVER_CLAIM blocks, vs the honest run. resid: everything else (other blocks, trajectory differences), reported as is.

| Scenario | Defense | loss_from_lies | damage | Σ bound | bound ok | reroute premium diff | resid | failure events |
|---|---|---|---|---|---|---|---|---|
| 1_honest | reputation | 0.0 | - | - | - | 0.0 | - | 0.0 |
| 2_always_lie | reputation | 1,367.3 | - | - | - | 0.0 | - | 0.0 |
| 3_farm_then_lie | reputation | 55.7 | - | - | - | 0.0 | - | 0.0 |
| 4_slow_drift | reputation | 861.0 | - | - | - | 0.0 | - | 0.0 |
| 5_price_bait | reputation | 2,725.5 | - | - | - | 0.0 | - | 0.0 |
| 6_vague | reputation | 1,093.8 | - | - | - | 0.0 | - | 0.0 |
| 7_far_deadlines | reputation | 1,356.2 | - | - | - | 0.0 | - | 0.0 |
| 8_claim_splitting | reputation | 1,377.0 | - | - | - | 0.0 | - | 0.0 |
| 9_noisy_honest | reputation | 560.5 | - | - | - | 0.0 | - | 0.0 |
| 10_farm_fail_refarm | reputation | 132.1 | - | - | - | 0.0 | - | 0.0 |
| 11_extraction_attack | reputation | 1,127.2 | - | - | - | 0.0 | - | 0.0 |
| 12_sybil_reentry | reputation | 2,217.5 | - | - | - | 0.0 | - | 0.0 |

## Reroute premium (honest S_main)

Absolute backup premium the defense's own reroutes cost in the honest scenario (not differenced).

| Defense | Reroute premium ($) |
|---|---|
| reputation | 0.0 |

## Utility (scenarios 1 and 9)

| Scenario | Defense | Cost | Extra vs none | Blocked S_main orders |
|---|---|---|---|---|
| 1_honest | reputation | 11,583.7 | - | 0.0 |
| 9_noisy_honest | reputation | 12,144.2 | - | 62.67 |

## Overhead per round

| Defense | Tokens | Latency (s) | Added tokens vs none | Added latency vs none |
|---|---|---|---|---|
| reputation | 0.0 | 0.0 | - | - |
