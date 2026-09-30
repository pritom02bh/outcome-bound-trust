Mean over seeds with a 95% CI (percentile bootstrap over seeds, 10,000 resamples). Seeds per row are given in the `seeds` column: a defense can have more seeds than another (extra seeds were run for some), and a utility cost needs the `none` run on the same seed. With few seeds the interval is coarse. $ per run.

## Attack loss per defense (loss from lies, mean of scenarios 2-12)

| defense | seeds | mean [95% CI] | per seed |
|---|---|---|---|
| obt | 3 | 327.8 [291.5, 375.6] | s1: 316.2, s2: 291.5, s3: 375.6 |

## Utility cost per defense (primary utility metric: cost − cost(none), honest S_main, same seed)

| defense | seeds | utility cost, honest [95% CI] | utility cost, noisy-honest [95% CI] | S_main unit share, honest | S_main orders blocked, honest |
|---|---|---|---|---|---|
| obt | 0 | - | - | 0.383 | 1.3 |

## Utility cost as a % of the honest run's total cost (cost(none, honest), same seed)

| defense | honest [95% CI] | noisy-honest [95% CI] |
|---|---|---|
| obt | - | - |

## Scenario 9 (noisy-honest) utility cost, every defense

Noisy-honest is an honest supplier with random delays: any cost above no defense is utility lost to false positives.

| defense | utility cost [95% CI] | S_main unit share | S_main orders blocked |
|---|---|---|---|
| obt | - | 0.204 | 5.0 |

## Loss from lies per scenario (mean [95% CI] over each defense's seeds, as above)

| scenario | obt |
|---|---|
| 1_honest | 0.0 [0.0, 0.0] |
| 2_always_lie | 499.8 [482.0, 514.5] |
| 3_farm_then_lie | 60.6 [-56.0, 248.2] |
| 4_slow_drift | 468.7 [440.0, 492.5] |
| 5_price_bait | 331.2 [315.0, 345.0] |
| 6_vague | 385.2 [369.0, 401.5] |
| 7_far_deadlines | 385.2 [369.0, 401.5] |
| 8_claim_splitting | 376.8 [354.0, 396.5] |
| 9_noisy_honest | 161.7 [117.5, 239.5] |
| 10_farm_fail_refarm | 51.8 [-34.5, 177.0] |
| 11_extraction_attack | 384.7 [368.5, 401.0] |
| 12_sybil_reentry | 499.8 [482.0, 514.5] |

## OBT damage vs bound (every OBT run with at least one failure event)

301 failure events in 14 runs; total damage $1,210.0 vs total bound $7,757.0; damage/bound per run: min -0.406, median 0.343, max 0.643; bound held in every run: True.

| scenario | runs | events | damage | Σ bound | Σ a-priori (budget) bound |
|---|---|---|---|---|---|
| 2_always_lie | 3 | 99 | 475.5 | 1,386.0 | 6,336.0 |
| 3_farm_then_lie | 1 | 1 | 135.0 | 210.0 | 978.8 |
| 4_slow_drift | 3 | 87 | 426.5 | 1,218.0 | 6,528.0 |
| 9_noisy_honest | 3 | 14 | -375.5 | 3,361.0 | 7,104.0 |
| 10_farm_fail_refarm | 1 | 1 | 73.0 | 196.0 | 1,129.4 |
| 12_sybil_reentry | 3 | 99 | 475.5 | 1,386.0 | 6,336.0 |
