## Loss from lies ($, cost minus honest-S_main cost on the same seed)

| Scenario | obt | rep-strict |
|---|---|---|
| 1_honest | 0.0 | 0.0 |
| 2_always_lie | 129.2 | 360.5 |
| 3_farm_then_lie | -10.2 | 0.0 |
| 9_noisy_honest | 0.7 | 4.7 |
| 12_sybil_reentry | 136.0 | 769.0 |

## Loss decomposition and bound (DESIGN §6)

loss_from_lies = damage + reroute_cost_diff + resid, every term relative to the honest run with the same defense and seed. damage: cost vs the same decisions with every relied-on promise kept; the bound Σ L_e applies to it (OBT only). reroute premium diff (reroute_cost_diff): extra backup premium on quantity rerouted after OVER_BUDGET/OVER_CLAIM blocks, vs the honest run. resid: everything else (other blocks, trajectory differences), reported as is.

| Scenario | Defense | loss_from_lies | damage | Σ bound | bound ok | reroute premium diff | resid | failure events |
|---|---|---|---|---|---|---|---|---|
| 1_honest | obt | 0.0 | 0.0 | 0.0 | yes | 0.0 | 0.0 | 0.0 |
| 1_honest | rep-strict | 0.0 | - | - | - | 0.0 | - | 0.0 |
| 2_always_lie | obt | 129.2 | 122.5 | 336.0 | yes | -3.0 | 9.7 | 24.0 |
| 2_always_lie | rep-strict | 360.5 | - | - | - | 0.0 | - | 0.0 |
| 3_farm_then_lie | obt | -10.2 | 4.5 | 14.0 | yes | -1.7 | -13.1 | 1.0 |
| 3_farm_then_lie | rep-strict | 0.0 | - | - | - | 0.0 | - | 0.0 |
| 9_noisy_honest | obt | 0.7 | 74.7 | 148.7 | yes | -3.0 | -71.0 | 3.3 |
| 9_noisy_honest | rep-strict | 4.7 | - | - | - | 0.0 | - | 0.0 |
| 12_sybil_reentry | obt | 136.0 | 131.3 | 350.0 | yes | -3.0 | 7.7 | 25.0 |
| 12_sybil_reentry | rep-strict | 769.0 | - | - | - | 0.0 | - | 0.0 |

## Reroute premium (honest S_main)

Absolute backup premium the defense's own reroutes cost in the honest scenario (not differenced).

| Defense | Reroute premium ($) |
|---|---|
| obt | 3.0 |
| rep-strict | 0.0 |

## Utility (scenarios 1 and 9)

| Scenario | Defense | Cost | Extra vs none | Blocked S_main orders |
|---|---|---|---|---|
| 1_honest | obt | 6,297.3 | - | 1.0 |
| 1_honest | rep-strict | 6,297.0 | - | 0.0 |
| 9_noisy_honest | obt | 6,298.0 | - | 0.0 |
| 9_noisy_honest | rep-strict | 6,301.7 | - | 0.67 |

## Overhead per round

| Defense | Tokens | Latency (s) | Added tokens vs none | Added latency vs none |
|---|---|---|---|---|
| obt | 1866.48 | 6.35 | - | - |
| rep-strict | 1346.57 | 5.15 | - | - |
