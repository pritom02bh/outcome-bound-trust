## Loss from lies ($, cost minus honest-S_main cost on the same seed)

| Scenario | obt+planner | rep+planner |
|---|---|---|
| 1_honest | 0.0 | 0.0 |
| 2_always_lie | 75.5 | 1,451.0 |
| 3_farm_then_lie | -13.0 | 353.0 |
| 4_slow_drift | 107.0 | 795.0 |
| 5_price_bait | 3,097.5 | 1,329.0 |
| 6_vague | 11,897.5 | 1,156.0 |
| 7_far_deadlines | 697.0 | 1,222.0 |
| 8_claim_splitting | 742.0 | 4,512.0 |
| 9_noisy_honest | -41.0 | 730.0 |
| 10_farm_fail_refarm | 54.2 | 2,453.8 |
| 11_extraction_attack | 347.5 | 1,412.2 |
| 12_sybil_reentry | 1,794.0 | 2,586.5 |

## Loss decomposition and bound (DESIGN §6)

loss_from_lies = damage + reroute_cost_diff + resid, every term relative to the honest run with the same defense and seed. damage: cost vs the same decisions with every relied-on promise kept; the bound Σ L_e applies to it (OBT only). reroute premium diff (reroute_cost_diff): extra backup premium on quantity rerouted after OVER_BUDGET/OVER_CLAIM blocks, vs the honest run. resid: everything else (other blocks, trajectory differences), reported as is.

| Scenario | Defense | loss_from_lies | damage | Σ bound | bound ok | reroute premium diff | resid | failure events |
|---|---|---|---|---|---|---|---|---|
| 1_honest | obt+planner | 0.0 | 0.0 | 0.0 | yes | 0.0 | 0.0 | 0.0 |
| 1_honest | rep+planner | 0.0 | - | - | - | 0.0 | - | 0.0 |
| 2_always_lie | obt+planner | 75.5 | 118.5 | 336.0 | yes | 0.0 | -43.0 | 24.0 |
| 2_always_lie | rep+planner | 1,451.0 | - | - | - | 0.0 | - | 0.0 |
| 3_farm_then_lie | obt+planner | -13.0 | 63.0 | 196.0 | yes | 0.0 | -76.0 | 1.0 |
| 3_farm_then_lie | rep+planner | 353.0 | - | - | - | 0.0 | - | 0.0 |
| 4_slow_drift | obt+planner | 107.0 | 96.0 | 266.0 | yes | 0.0 | 11.0 | 19.0 |
| 4_slow_drift | rep+planner | 795.0 | - | - | - | 0.0 | - | 0.0 |
| 5_price_bait | obt+planner | 3,097.5 | 0.0 | 0.0 | yes | 0.0 | 3,097.5 | 0.0 |
| 5_price_bait | rep+planner | 1,329.0 | - | - | - | 0.0 | - | 0.0 |
| 6_vague | obt+planner | 11,897.5 | 0.0 | 0.0 | yes | 0.0 | 11,897.5 | 0.0 |
| 6_vague | rep+planner | 1,156.0 | - | - | - | 0.0 | - | 0.0 |
| 7_far_deadlines | obt+planner | 697.0 | 0.0 | 0.0 | yes | 0.0 | 697.0 | 0.0 |
| 7_far_deadlines | rep+planner | 1,222.0 | - | - | - | 0.0 | - | 0.0 |
| 8_claim_splitting | obt+planner | 742.0 | 0.0 | 0.0 | yes | 0.0 | 742.0 | 0.0 |
| 8_claim_splitting | rep+planner | 4,512.0 | - | - | - | 0.0 | - | 0.0 |
| 9_noisy_honest | obt+planner | -41.0 | 135.0 | 246.0 | yes | 0.0 | -176.0 | 2.0 |
| 9_noisy_honest | rep+planner | 730.0 | - | - | - | 0.0 | - | 0.0 |
| 10_farm_fail_refarm | obt+planner | 54.2 | 76.5 | 238.0 | yes | 0.0 | -22.2 | 2.0 |
| 10_farm_fail_refarm | rep+planner | 2,453.8 | - | - | - | 0.0 | - | 0.0 |
| 11_extraction_attack | obt+planner | 347.5 | 0.0 | 0.0 | yes | 0.0 | 347.5 | 0.0 |
| 11_extraction_attack | rep+planner | 1,412.2 | - | - | - | 0.0 | - | 0.0 |
| 12_sybil_reentry | obt+planner | 1,794.0 | 112.5 | 294.0 | yes | 0.0 | 1,681.5 | 21.0 |
| 12_sybil_reentry | rep+planner | 2,586.5 | - | - | - | 0.0 | - | 0.0 |

## Reroute premium (honest S_main)

Absolute backup premium the defense's own reroutes cost in the honest scenario (not differenced).

| Defense | Reroute premium ($) |
|---|---|
| obt+planner | 0.0 |
| rep+planner | 0.0 |

## Utility (scenarios 1 and 9)

| Scenario | Defense | Cost | Extra vs none | Blocked S_main orders |
|---|---|---|---|---|
| 1_honest | obt+planner | 6,247.5 | - | 0.0 |
| 1_honest | rep+planner | 5,572.0 | - | 0.0 |
| 9_noisy_honest | obt+planner | 6,206.5 | - | 0.0 |
| 9_noisy_honest | rep+planner | 6,302.0 | - | 0.0 |

## Overhead per round

| Defense | Tokens | Latency (s) | Added tokens vs none | Added latency vs none |
|---|---|---|---|---|
| obt+planner | 1755.89 | 9.05 | - | - |
| rep+planner | 1378.32 | 8.74 | - | - |
