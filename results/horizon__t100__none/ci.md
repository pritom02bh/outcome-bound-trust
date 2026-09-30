Mean over seeds with a 95% CI (percentile bootstrap over seeds, 10,000 resamples). Seeds per row are given in the `seeds` column: a defense can have more seeds than another (extra seeds were run for some), and a utility cost needs the `none` run on the same seed. With few seeds the interval is coarse. $ per run.

## Attack loss per defense (loss from lies, mean of scenarios 2-12)

| defense | seeds | mean [95% CI] | per seed |
|---|---|---|---|
| none | 3 | 13,939.2 [13,856.1, 14,053.6] | s1: 13,908.0, s2: 13,856.1, s3: 14,053.6 |

## Utility cost per defense (primary utility metric: cost − cost(none), honest S_main, same seed)

| defense | seeds | utility cost, honest [95% CI] | utility cost, noisy-honest [95% CI] | S_main unit share, honest | S_main orders blocked, honest |
|---|---|---|---|---|---|
| none | 3 | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.919 | 0.0 |

## Utility cost as a % of the honest run's total cost (cost(none, honest), same seed)

| defense | honest [95% CI] | noisy-honest [95% CI] |
|---|---|---|
| none | 0.00% [0.00, 0.00] | 0.00% [0.00, 0.00] |

## Scenario 9 (noisy-honest) utility cost, every defense

Noisy-honest is an honest supplier with random delays: any cost above no defense is utility lost to false positives.

| defense | utility cost [95% CI] | S_main unit share | S_main orders blocked |
|---|---|---|---|
| none | 0.0 [0.0, 0.0] | 0.919 | 0.0 |

## Loss from lies per scenario (mean [95% CI] over each defense's seeds, as above)

| scenario | none |
|---|---|
| 1_honest | 0.0 [0.0, 0.0] |
| 2_always_lie | 22,551.3 [22,227.5, 22,862.5] |
| 3_farm_then_lie | 55.7 [51.5, 61.8] |
| 4_slow_drift | 13,314.7 [13,207.5, 13,486.0] |
| 5_price_bait | 2,725.5 [2,707.5, 2,746.5] |
| 6_vague | 9,248.5 [8,981.0, 9,550.5] |
| 7_far_deadlines | 22,057.3 [21,734.2, 22,368.2] |
| 8_claim_splitting | 52,001.3 [51,218.5, 53,273.0] |
| 9_noisy_honest | -93.8 [-106.5, -76.5] |
| 10_farm_fail_refarm | 132.1 [104.8, 175.2] |
| 11_extraction_attack | 8,787.5 [8,547.2, 9,072.8] |
| 12_sybil_reentry | 22,551.3 [22,227.5, 22,862.5] |

## OBT damage vs bound (every OBT run with at least one failure event)

0 failure events in 0 runs; total damage $0.0 vs total bound $0.0; damage/bound per run: min None, median None, max None; bound held in every run: True.

| scenario | runs | events | damage | Σ bound | Σ a-priori (budget) bound |
|---|---|---|---|---|---|
