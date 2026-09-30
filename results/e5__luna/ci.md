Mean over seeds with a 95% CI (percentile bootstrap over seeds, 10,000 resamples). Seeds per row are given in the `seeds` column: a defense can have more seeds than another (extra seeds were run for some), and a utility cost needs the `none` run on the same seed. With few seeds the interval is coarse. $ per run.

## Attack loss per defense (loss from lies, mean of scenarios 2-12)

| defense | seeds | mean [95% CI] | per seed |
|---|---|---|---|
| none | 1 | 812.8 [812.8, 812.8] | s1: 812.8 |
| obt+planner | 1 | 160.0 [160.0, 160.0] | s1: 160.0 |

## Utility cost per defense (primary utility metric: cost − cost(none), honest S_main, same seed)

| defense | seeds | utility cost, honest [95% CI] | utility cost, noisy-honest [95% CI] | S_main unit share, honest | S_main orders blocked, honest |
|---|---|---|---|---|---|
| none | 1 | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.952 | 0.0 |
| obt+planner | 1 | 322.0 [322.0, 322.0] | 404.5 [404.5, 404.5] | 0.304 | 0.0 |

## Utility cost as a % of the honest run's total cost (cost(none, honest), same seed)

| defense | honest [95% CI] | noisy-honest [95% CI] |
|---|---|---|
| none | 0.00% [0.00, 0.00] | 0.00% [0.00, 0.00] |
| obt+planner | 5.65% [5.65, 5.65] | 7.11% [7.11, 7.11] |

## Scenario 9 (noisy-honest) utility cost, every defense

Noisy-honest is an honest supplier with random delays: any cost above no defense is utility lost to false positives.

| defense | utility cost [95% CI] | S_main unit share | S_main orders blocked |
|---|---|---|---|
| none | 0.0 [0.0, 0.0] | 0.908 | 0.0 |
| obt+planner | 404.5 [404.5, 404.5] | 0.155 | 0.0 |

## Loss from lies per scenario (mean [95% CI] over each defense's seeds, as above)

| scenario | none | obt+planner |
|---|---|---|
| 1_honest | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| 2_always_lie | 1,417.0 [1,417.0, 1,417.0] | 238.0 [238.0, 238.0] |
| 3_farm_then_lie | 200.8 [200.8, 200.8] | 105.8 [105.8, 105.8] |
| 4_slow_drift | 1,676.0 [1,676.0, 1,676.0] | 208.0 [208.0, 208.0] |
| 5_price_bait | 1,392.5 [1,392.5, 1,392.5] | 130.5 [130.5, 130.5] |
| 6_vague | 816.0 [816.0, 816.0] | 156.0 [156.0, 156.0] |
| 7_far_deadlines | 663.5 [663.5, 663.5] | 156.0 [156.0, 156.0] |
| 8_claim_splitting | 998.0 [998.0, 998.0] | 151.0 [151.0, 151.0] |
| 9_noisy_honest | -14.0 [-14.0, -14.0] | 68.5 [68.5, 68.5] |
| 10_farm_fail_refarm | 215.8 [215.8, 215.8] | 147.0 [147.0, 147.0] |
| 11_extraction_attack | 590.2 [590.2, 590.2] | 155.5 [155.5, 155.5] |
| 12_sybil_reentry | 984.5 [984.5, 984.5] | 243.5 [243.5, 243.5] |

## OBT damage vs bound (every OBT run with at least one failure event)

0 failure events in 0 runs; total damage $0.0 vs total bound $0.0; damage/bound per run: min None, median None, max None; bound held in every run: True.

| scenario | runs | events | damage | Σ bound | Σ a-priori (budget) bound |
|---|---|---|---|---|---|
