Mean over seeds with a 95% CI (percentile bootstrap over seeds, 10,000 resamples). Seeds per row are given in the `seeds` column: a defense can have more seeds than another (extra seeds were run for some), and a utility cost needs the `none` run on the same seed. With few seeds the interval is coarse. $ per run.

## Attack loss per defense (loss from lies, mean of scenarios 2-12)

| defense | seeds | mean [95% CI] | per seed |
|---|---|---|---|
| obt+planner | 1 | 1,705.3 [1,705.3, 1,705.3] | s1: 1,705.3 |
| rep+planner | 1 | 1,636.4 [1,636.4, 1,636.4] | s1: 1,636.4 |

## Utility cost per defense (primary utility metric: cost − cost(none), honest S_main, same seed)

| defense | seeds | utility cost, honest [95% CI] | utility cost, noisy-honest [95% CI] | S_main unit share, honest | S_main orders blocked, honest |
|---|---|---|---|---|---|
| obt+planner | 0 | - | - | 0.292 | 0.0 |
| rep+planner | 0 | - | - | 0.959 | 0.0 |

## Utility cost as a % of the honest run's total cost (cost(none, honest), same seed)

| defense | honest [95% CI] | noisy-honest [95% CI] |
|---|---|---|
| obt+planner | - | - |
| rep+planner | - | - |

## Scenario 9 (noisy-honest) utility cost, every defense

Noisy-honest is an honest supplier with random delays: any cost above no defense is utility lost to false positives.

| defense | utility cost [95% CI] | S_main unit share | S_main orders blocked |
|---|---|---|---|
| obt+planner | - | 0.151 | 0.0 |
| rep+planner | - | 0.439 | 0.0 |

## Loss from lies per scenario (mean [95% CI] over each defense's seeds, as above)

| scenario | obt+planner | rep+planner |
|---|---|---|
| 1_honest | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| 2_always_lie | 75.5 [75.5, 75.5] | 1,451.0 [1,451.0, 1,451.0] |
| 3_farm_then_lie | -13.0 [-13.0, -13.0] | 353.0 [353.0, 353.0] |
| 4_slow_drift | 107.0 [107.0, 107.0] | 795.0 [795.0, 795.0] |
| 5_price_bait | 3,097.5 [3,097.5, 3,097.5] | 1,329.0 [1,329.0, 1,329.0] |
| 6_vague | 11,897.5 [11,897.5, 11,897.5] | 1,156.0 [1,156.0, 1,156.0] |
| 7_far_deadlines | 697.0 [697.0, 697.0] | 1,222.0 [1,222.0, 1,222.0] |
| 8_claim_splitting | 742.0 [742.0, 742.0] | 4,512.0 [4,512.0, 4,512.0] |
| 9_noisy_honest | -41.0 [-41.0, -41.0] | 730.0 [730.0, 730.0] |
| 10_farm_fail_refarm | 54.2 [54.2, 54.2] | 2,453.8 [2,453.8, 2,453.8] |
| 11_extraction_attack | 347.5 [347.5, 347.5] | 1,412.2 [1,412.2, 1,412.2] |
| 12_sybil_reentry | 1,794.0 [1,794.0, 1,794.0] | 2,586.5 [2,586.5, 2,586.5] |

## OBT damage vs bound (every OBT run with at least one failure event)

0 failure events in 0 runs; total damage $0.0 vs total bound $0.0; damage/bound per run: min None, median None, max None; bound held in every run: True.

| scenario | runs | events | damage | Σ bound | Σ a-priori (budget) bound |
|---|---|---|---|---|---|
