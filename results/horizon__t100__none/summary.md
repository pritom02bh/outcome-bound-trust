## Loss from lies ($, cost minus honest-S_main cost on the same seed)

| Scenario | none |
|---|---|
| 1_honest | 0.0 |
| 2_always_lie | 22,551.3 |
| 3_farm_then_lie | 55.7 |
| 4_slow_drift | 13,314.7 |
| 5_price_bait | 2,725.5 |
| 6_vague | 9,248.5 |
| 7_far_deadlines | 22,057.3 |
| 8_claim_splitting | 52,001.3 |
| 9_noisy_honest | -93.8 |
| 10_farm_fail_refarm | 132.1 |
| 11_extraction_attack | 8,787.5 |
| 12_sybil_reentry | 22,551.3 |

## Loss decomposition and bound (DESIGN §6)

loss_from_lies = damage + reroute_cost_diff + resid, every term relative to the honest run with the same defense and seed. damage: cost vs the same decisions with every relied-on promise kept; the bound Σ L_e applies to it (OBT only). reroute_cost_diff: extra backup premium on quantity rerouted after OVER_BUDGET/OVER_CLAIM blocks, vs the honest run. resid: everything else (other blocks, trajectory differences), reported as is.

| Scenario | Defense | loss_from_lies | damage | Σ bound | bound ok | reroute_cost_diff | resid | failure events |
|---|---|---|---|---|---|---|---|---|
| 1_honest | none | 0.0 | - | - | - | 0.0 | - | 0.0 |
| 2_always_lie | none | 22,551.3 | - | - | - | 0.0 | - | 0.0 |
| 3_farm_then_lie | none | 55.7 | - | - | - | 0.0 | - | 0.0 |
| 4_slow_drift | none | 13,314.7 | - | - | - | 0.0 | - | 0.0 |
| 5_price_bait | none | 2,725.5 | - | - | - | 0.0 | - | 0.0 |
| 6_vague | none | 9,248.5 | - | - | - | 0.0 | - | 0.0 |
| 7_far_deadlines | none | 22,057.3 | - | - | - | 0.0 | - | 0.0 |
| 8_claim_splitting | none | 52,001.3 | - | - | - | 0.0 | - | 0.0 |
| 9_noisy_honest | none | -93.8 | - | - | - | 0.0 | - | 0.0 |
| 10_farm_fail_refarm | none | 132.1 | - | - | - | 0.0 | - | 0.0 |
| 11_extraction_attack | none | 8,787.5 | - | - | - | 0.0 | - | 0.0 |
| 12_sybil_reentry | none | 22,551.3 | - | - | - | 0.0 | - | 0.0 |

## Price of safety (honest S_main)

Absolute backup premium the defense's own reroutes cost in the honest scenario (not differenced).

| Defense | Price of safety ($) |
|---|---|
| none | 0.0 |

## Utility (scenarios 1 and 9)

| Scenario | Defense | Cost | Extra vs none | Blocked S_main orders |
|---|---|---|---|---|
| 1_honest | none | 11,583.7 | 0.0 | 0.0 |
| 9_noisy_honest | none | 11,489.8 | 0.0 | 0.0 |

## Overhead per round

| Defense | Tokens | Latency (s) | Added tokens vs none | Added latency vs none |
|---|---|---|---|---|
| none | 123.14 | 1.0 | 0.0 | 0.0 |
