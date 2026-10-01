Mean over seeds with a 95% CI (percentile bootstrap over seeds, 10,000 resamples). Seeds per row are given in the `seeds` column: a defense can have more seeds than another (extra seeds were run for some), and a utility cost needs the `none` run on the same seed. With few seeds the interval is coarse. $ per run.

## Attack loss per defense (loss from lies, mean of scenarios 2-12)

| defense | seeds | mean [95% CI] | per seed |
|---|---|---|---|
| none | 3 | 999.9 [812.8, 1,096.3] | s1: 812.8, s2: 1,090.6, s3: 1,096.3 |
| obt+planner | 3 | 176.9 [160.0, 189.5] | s1: 160.0, s2: 181.1, s3: 189.5 |

## Utility cost per defense (primary utility metric: cost − cost(none), honest S_main, same seed)

| defense | seeds | utility cost, honest [95% CI] | utility cost, noisy-honest [95% CI] | S_main unit share, honest | S_main orders blocked, honest |
|---|---|---|---|---|---|
| none | 3 | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.932 | 0.0 |
| obt+planner | 3 | 342.2 [322.0, 359.0] | 417.8 [403.0, 446.0] | 0.295 | 0.0 |

## Utility cost as a % of the honest run's total cost (cost(none, honest), same seed)

| defense | honest [95% CI] | noisy-honest [95% CI] |
|---|---|---|
| none | 0.00% [0.00, 0.00] | 0.00% [0.00, 0.00] |
| obt+planner | 5.87% [5.65, 6.18] | 7.17% [6.93, 7.47] |

## Scenario 9 (noisy-honest) utility cost, every defense

Noisy-honest is an honest supplier with random delays: any cost above no defense is utility lost to false positives.

| defense | utility cost [95% CI] | S_main unit share | S_main orders blocked |
|---|---|---|---|
| none | 0.0 [0.0, 0.0] | 0.887 | 0.0 |
| obt+planner | 417.8 [403.0, 446.0] | 0.152 | 0.0 |

## Loss from lies per scenario (mean [95% CI] over each defense's seeds, as above)

| scenario | none | obt+planner |
|---|---|---|
| 1_honest | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| 2_always_lie | 1,951.2 [1,417.0, 2,566.5] | 253.3 [238.0, 267.0] |
| 3_farm_then_lie | 180.5 [144.8, 200.8] | 163.4 [105.8, 224.8] |
| 4_slow_drift | 973.2 [517.5, 1,676.0] | 215.5 [207.0, 231.5] |
| 5_price_bait | 1,430.0 [1,392.5, 1,449.5] | 138.8 [130.5, 147.0] |
| 6_vague | 906.2 [816.0, 982.0] | 168.5 [156.0, 180.0] |
| 7_far_deadlines | 1,083.7 [663.5, 1,454.8] | 168.5 [156.0, 180.0] |
| 8_claim_splitting | 1,581.2 [998.0, 1,904.5] | 158.5 [151.0, 164.5] |
| 9_noisy_honest | -4.5 [-14.0, 9.5] | 71.2 [53.5, 91.5] |
| 10_farm_fail_refarm | 272.4 [215.8, 365.2] | 179.5 [147.0, 208.0] |
| 11_extraction_attack | 1,257.2 [590.2, 1,702.0] | 168.0 [155.5, 179.5] |
| 12_sybil_reentry | 1,368.0 [984.5, 1,791.0] | 260.2 [243.5, 275.0] |

## OBT damage vs bound (every OBT run with at least one failure event)

0 failure events in 0 runs; total damage $0.0 vs total bound $0.0; damage/bound per run: min None, median None, max None; bound held in every run: True.

| scenario | runs | events | damage | Σ bound | Σ a-priori (budget) bound |
|---|---|---|---|---|---|
