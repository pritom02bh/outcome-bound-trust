## Loss from lies ($, cost minus honest-S_main cost on the same seed)

| Scenario | obt+planner | rep-n18 | rep+planner |
|---|---|---|---|
| 1_honest | 0.0 | 0.0 | 0.0 |
| 2_always_lie | 184.8 | 647.8 | 1,002.1 |
| 3_farm_then_lie | 86.5 | 109.3 | 135.3 |
| 4_slow_drift | 156.0 | 409.0 | 489.5 |
| 5_price_bait | 70.1 | 868.3 | 750.7 |
| 6_vague | 100.1 | 432.3 | 406.4 |
| 7_far_deadlines | 100.3 | 712.6 | 982.6 |
| 8_claim_splitting | 89.4 | 648.8 | 1,075.5 |
| 9_noisy_honest | 49.5 | 182.7 | 83.9 |
| 10_farm_fail_refarm | 98.1 | 304.3 | 222.2 |
| 11_extraction_attack | 100.2 | 786.2 | 558.5 |
| 12_sybil_reentry | 190.1 | 968.5 | 1,460.7 |

## Loss decomposition and bound (DESIGN §6)

loss_from_lies = damage + reroute_cost_diff + resid, every term relative to the honest run with the same defense and seed. damage: cost vs the same decisions with every relied-on promise kept; the bound Σ L_e applies to it (OBT only). reroute premium diff (reroute_cost_diff): extra backup premium on quantity rerouted after OVER_BUDGET/OVER_CLAIM blocks, vs the honest run. resid: everything else (other blocks, trajectory differences), reported as is.

| Scenario | Defense | loss_from_lies | damage | Σ bound | bound ok | reroute premium diff | resid | failure events |
|---|---|---|---|---|---|---|---|---|
| 1_honest | obt+planner | 0.0 | 0.0 | 0.0 | yes | 0.0 | 0.0 | 0.0 |
| 1_honest | rep-n18 | 0.0 | - | - | - | 0.0 | - | 0.0 |
| 1_honest | rep+planner | 0.0 | - | - | - | 0.0 | - | 0.0 |
| 2_always_lie | obt+planner | 184.8 | 124.4 | 336.0 | yes | 0.0 | 60.4 | 24.0 |
| 2_always_lie | rep-n18 | 647.8 | - | - | - | 0.0 | - | 0.0 |
| 2_always_lie | rep+planner | 1,002.1 | - | - | - | 0.0 | - | 0.0 |
| 3_farm_then_lie | obt+planner | 86.5 | 51.4 | 114.8 | yes | 0.0 | 35.1 | 1.0 |
| 3_farm_then_lie | rep-n18 | 109.3 | - | - | - | 0.0 | - | 0.0 |
| 3_farm_then_lie | rep+planner | 135.3 | - | - | - | 0.0 | - | 0.0 |
| 4_slow_drift | obt+planner | 156.0 | 96.4 | 266.0 | yes | 0.0 | 59.6 | 19.0 |
| 4_slow_drift | rep-n18 | 409.0 | - | - | - | 0.0 | - | 0.0 |
| 4_slow_drift | rep+planner | 489.5 | - | - | - | 0.0 | - | 0.0 |
| 5_price_bait | obt+planner | 70.1 | 0.0 | 0.0 | yes | 0.0 | 70.1 | 0.0 |
| 5_price_bait | rep-n18 | 868.3 | - | - | - | 0.0 | - | 0.0 |
| 5_price_bait | rep+planner | 750.7 | - | - | - | 0.0 | - | 0.0 |
| 6_vague | obt+planner | 100.1 | 0.0 | 0.0 | yes | 0.0 | 100.1 | 0.0 |
| 6_vague | rep-n18 | 432.3 | - | - | - | 0.0 | - | 0.0 |
| 6_vague | rep+planner | 406.4 | - | - | - | 0.0 | - | 0.0 |
| 7_far_deadlines | obt+planner | 100.3 | 0.0 | 0.0 | yes | 0.0 | 100.3 | 0.0 |
| 7_far_deadlines | rep-n18 | 712.6 | - | - | - | 0.0 | - | 0.0 |
| 7_far_deadlines | rep+planner | 982.6 | - | - | - | 0.0 | - | 0.0 |
| 8_claim_splitting | obt+planner | 89.4 | 0.0 | 0.0 | yes | 0.0 | 89.4 | 0.0 |
| 8_claim_splitting | rep-n18 | 648.8 | - | - | - | 0.0 | - | 0.0 |
| 8_claim_splitting | rep+planner | 1,075.5 | - | - | - | 0.0 | - | 0.0 |
| 9_noisy_honest | obt+planner | 49.5 | 93.6 | 233.8 | yes | 0.0 | -44.1 | 2.8 |
| 9_noisy_honest | rep-n18 | 182.7 | - | - | - | 0.0 | - | 0.0 |
| 9_noisy_honest | rep+planner | 83.9 | - | - | - | 0.0 | - | 0.0 |
| 10_farm_fail_refarm | obt+planner | 98.1 | 58.0 | 168.0 | yes | 0.0 | 40.1 | 2.0 |
| 10_farm_fail_refarm | rep-n18 | 304.3 | - | - | - | 0.0 | - | 0.0 |
| 10_farm_fail_refarm | rep+planner | 222.2 | - | - | - | 0.0 | - | 0.0 |
| 11_extraction_attack | obt+planner | 100.2 | 0.0 | 0.0 | yes | 0.0 | 100.2 | 0.0 |
| 11_extraction_attack | rep-n18 | 786.2 | - | - | - | 0.0 | - | 0.0 |
| 11_extraction_attack | rep+planner | 558.5 | - | - | - | 0.0 | - | 0.0 |
| 12_sybil_reentry | obt+planner | 190.1 | 130.5 | 350.0 | yes | 0.0 | 59.6 | 25.0 |
| 12_sybil_reentry | rep-n18 | 968.5 | - | - | - | 0.0 | - | 0.0 |
| 12_sybil_reentry | rep+planner | 1,460.7 | - | - | - | 0.0 | - | 0.0 |

## Reroute premium (honest S_main)

Absolute backup premium the defense's own reroutes cost in the honest scenario (not differenced).

| Defense | Reroute premium ($) |
|---|---|
| obt+planner | 0.0 |
| rep-n18 | 0.0 |
| rep+planner | 0.0 |

## Utility (scenarios 1 and 9)

| Scenario | Defense | Cost | Extra vs none | Blocked S_main orders |
|---|---|---|---|---|
| 1_honest | obt+planner | 6,242.5 | - | 0.0 |
| 1_honest | rep-n18 | 5,961.0 | - | 1.0 |
| 1_honest | rep+planner | 6,016.9 | - | 0.0 |
| 9_noisy_honest | obt+planner | 6,292.0 | - | 0.0 |
| 9_noisy_honest | rep-n18 | 6,143.7 | - | 7.6 |
| 9_noisy_honest | rep+planner | 6,100.8 | - | 0.0 |

## Overhead per round

| Defense | Tokens | Latency (s) | Added tokens vs none | Added latency vs none |
|---|---|---|---|---|
| obt+planner | 1677.63 | 6.38 | - | - |
| rep-n18 | 1332.04 | 5.64 | - | - |
| rep+planner | 1324.33 | 5.49 | - | - |
