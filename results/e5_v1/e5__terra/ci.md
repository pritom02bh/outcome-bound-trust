Mean over seeds with a 95% CI (percentile bootstrap over seeds, 10,000 resamples). Seeds per row are given in the `seeds` column: a defense can have more seeds than another (extra seeds were run for some), and a utility cost needs the `none` run on the same seed. With few seeds the interval is coarse. $ per run.

## Attack loss per defense (loss from lies, mean of scenarios 2-12)

| defense | seeds | mean [95% CI] | per seed |
|---|---|---|---|
| obt+planner | 1 | 158.0 [158.0, 158.0] | s1: 158.0 |

## Utility cost per defense (primary utility metric: cost − cost(none), honest S_main, same seed)

| defense | seeds | utility cost, honest [95% CI] | utility cost, noisy-honest [95% CI] | S_main unit share, honest | S_main orders blocked, honest |
|---|---|---|---|---|---|
| obt+planner | 0 | - | - | 0.298 | 0.0 |

## Utility cost as a % of the honest run's total cost (cost(none, honest), same seed)

| defense | honest [95% CI] | noisy-honest [95% CI] |
|---|---|---|
| obt+planner | - | - |

## Scenario 9 (noisy-honest) utility cost, every defense

Noisy-honest is an honest supplier with random delays: any cost above no defense is utility lost to false positives.

| defense | utility cost [95% CI] | S_main unit share | S_main orders blocked |
|---|---|---|---|
| obt+planner | - | 0.155 | 0.0 |

## Loss from lies per scenario (mean [95% CI] over each defense's seeds, as above)

| scenario | obt+planner |
|---|---|
| 1_honest | 0.0 [0.0, 0.0] |
| 2_always_lie | 236.0 [236.0, 236.0] |
| 3_farm_then_lie | 103.8 [103.8, 103.8] |
| 4_slow_drift | 206.0 [206.0, 206.0] |
| 5_price_bait | 128.5 [128.5, 128.5] |
| 6_vague | 154.0 [154.0, 154.0] |
| 7_far_deadlines | 154.0 [154.0, 154.0] |
| 8_claim_splitting | 149.0 [149.0, 149.0] |
| 9_noisy_honest | 66.5 [66.5, 66.5] |
| 10_farm_fail_refarm | 145.0 [145.0, 145.0] |
| 11_extraction_attack | 153.5 [153.5, 153.5] |
| 12_sybil_reentry | 241.5 [241.5, 241.5] |

## OBT damage vs bound (every OBT run with at least one failure event)

0 failure events in 0 runs; total damage $0.0 vs total bound $0.0; damage/bound per run: min None, median None, max None; bound held in every run: True.

| scenario | runs | events | damage | Σ bound | Σ a-priori (budget) bound |
|---|---|---|---|---|---|
