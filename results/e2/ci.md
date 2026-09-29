Mean over seeds with a 95% CI (percentile bootstrap over seeds, 10,000 resamples). Seeds per row are given in the `seeds` column: a defense can have more seeds than another (extra seeds were run for some), and a utility cost needs the `none` run on the same seed. With few seeds the interval is coarse. $ per run.

## Attack loss per defense (loss from lies, mean of scenarios 2-12)

| defense | seeds | mean [95% CI] | per seed |
|---|---|---|---|
| obt | 5 | 43.1 [37.0, 50.5] | s1: 32.8, s2: 40.1, s3: 56.3, s4: 43.4, s5: 43.2 |
| none | 5 | 1,357.1 [391.1, 2,313.6] | s1: 2,127.5, s2: 2,469.5, s3: 2,274.6, s4: -43.0, s5: -43.0 |
| provenance | 3 | 1,649.9 [1,471.5, 1,903.2] | s1: 1,574.9, s2: 1,471.5, s3: 1,903.2 |
| llm_selfcheck | 3 | 740.8 [520.5, 934.1] | s1: 520.5, s2: 934.1, s3: 767.8 |
| rep-strict | 5 | 169.0 [130.4, 215.9] | s1: 201.1, s2: 248.0, s3: 122.0, s4: 139.8, s5: 134.2 |
| rep-default | 5 | 483.3 [411.7, 555.5] | s1: 563.8, s2: 459.1, s3: 368.7, s4: 594.2, s5: 430.9 |

## Utility cost per defense (primary utility metric: cost − cost(none), honest S_main, same seed)

| defense | seeds | utility cost, honest [95% CI] | utility cost, noisy-honest [95% CI] | S_main unit share, honest | S_main orders blocked, honest |
|---|---|---|---|---|---|
| obt | 5 | 324.6 [288.5, 363.1] | 356.5 [308.7, 395.0] | 0.055 | 0.4 |
| none | 5 | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.663 | 0.0 |
| provenance | 3 | 39.7 [26.0, 55.0] | 74.7 [54.0, 102.5] | 0.534 | 0.0 |
| llm_selfcheck | 3 | 75.3 [44.0, 99.0] | 125.8 [102.0, 172.5] | 0.475 | 7.3 |
| rep-strict | 5 | 320.9 [288.2, 358.9] | 355.5 [308.5, 403.4] | 0.069 | 1.8 |
| rep-default | 5 | 46.1 [-51.4, 124.8] | 329.4 [269.4, 378.6] | 0.556 | 1.8 |

## Utility cost as a % of the honest run's total cost (cost(none, honest), same seed)

| defense | honest [95% CI] | noisy-honest [95% CI] |
|---|---|---|
| obt | 5.43% [4.86, 6.03] | 6.00% [5.15, 6.68] |
| none | 0.00% [0.00, 0.00] | 0.00% [0.00, 0.00] |
| provenance | 0.66% [0.44, 0.92] | 1.25% [0.92, 1.73] |
| llm_selfcheck | 1.26% [0.74, 1.68] | 2.11% [1.68, 2.91] |
| rep-strict | 5.36% [4.82, 6.01] | 5.98% [5.23, 6.74] |
| rep-default | 0.75% [-0.89, 2.06] | 5.53% [4.56, 6.37] |

## Scenario 9 (noisy-honest) utility cost, every defense

Noisy-honest is an honest supplier with random delays: any cost above no defense is utility lost to false positives.

| defense | utility cost [95% CI] | S_main unit share | S_main orders blocked |
|---|---|---|---|
| obt | 356.5 [308.7, 395.0] | 0.050 | 0.2 |
| none | 0.0 [0.0, 0.0] | 0.660 | 0.0 |
| provenance | 74.7 [54.0, 102.5] | 0.493 | 0.0 |
| llm_selfcheck | 125.8 [102.0, 172.5] | 0.395 | 8.0 |
| rep-strict | 355.5 [308.5, 403.4] | 0.062 | 10.8 |
| rep-default | 329.4 [269.4, 378.6] | 0.101 | 10.8 |

## Loss from lies per scenario (mean [95% CI] over each defense's seeds, as above)

| scenario | obt | none | provenance | llm_selfcheck | rep-strict | rep-default |
|---|---|---|---|---|---|---|
| 1_honest | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| 2_always_lie | 121.3 [112.0, 130.6] | 7,107.3 [6,865.5, 7,268.0] | 5,562.3 [4,101.0, 7,270.0] | 1,944.5 [1,223.5, 2,332.5] | 305.1 [205.5, 371.6] | 579.9 [435.1, 699.7] |
| 3_farm_then_lie | -0.5 [-8.2, 5.0] | 57.7 [32.0, 100.8] | 99.0 [57.2, 128.8] | 96.0 [-4.0, 205.5] | 0.0 [0.0, 0.0] | 98.0 [-0.8, 214.7] |
| 4_slow_drift | 91.3 [79.7, 102.9] | 1,778.8 [1,391.0, 2,118.0] | 1,103.3 [990.5, 1,272.0] | 456.8 [316.0, 609.5] | 0.0 [0.0, 0.0] | 230.3 [167.4, 315.8] |
| 5_price_bait | -19.5 [-23.9, -14.4] | 808.7 [754.5, 860.0] | 691.0 [609.5, 743.0] | 650.0 [580.5, 747.0] | 109.4 [87.5, 129.8] | 860.3 [747.4, 971.5] |
| 6_vague | 36.5 [29.5, 44.2] | 611.7 [468.5, 777.0] | 647.5 [506.0, 823.5] | 272.8 [217.0, 342.5] | 78.3 [49.5, 129.7] | 353.1 [289.4, 426.6] |
| 7_far_deadlines | 36.6 [29.5, 44.2] | 5,627.8 [5,529.0, 5,776.0] | 4,480.9 [4,124.2, 4,725.0] | 1,452.6 [1,025.2, 2,264.8] | 388.8 [330.6, 483.1] | 663.5 [575.5, 751.6] |
| 8_claim_splitting | 43.6 [20.0, 67.2] | 632.7 [414.5, 893.5] | 446.8 [341.5, 628.5] | 337.5 [221.0, 552.5] | 1.4 [-9.0, 18.1] | 656.1 [532.6, 790.7] |
| 9_noisy_honest | -2.8 [-15.0, 8.2] | -34.7 [-46.4, -19.9] | 5.8 [-4.0, 22.0] | 21.3 [-10.0, 77.0] | -0.1 [-10.5, 10.2] | 248.6 [180.3, 347.4] |
| 10_farm_fail_refarm | 6.3 [4.8, 7.7] | 193.4 [160.2, 253.0] | 236.1 [218.2, 261.5] | 172.7 [9.5, 354.0] | 0.0 [0.0, 0.0] | 100.6 [-26.2, 227.4] |
| 11_extraction_attack | 36.0 [29.0, 43.7] | 706.8 [330.2, 1,373.5] | 726.3 [383.2, 1,111.0] | 260.2 [199.0, 322.5] | 153.4 [69.1, 273.6] | 428.5 [324.9, 532.1] |
| 12_sybil_reentry | 125.7 [116.4, 134.6] | 7,700.5 [6,233.5, 9,425.0] | 4,149.5 [3,140.5, 5,074.5] | 2,484.3 [1,596.5, 3,005.5] | 823.0 [641.2, 1,023.8] | 1,097.8 [907.7, 1,287.9] |

## OBT damage vs bound (every OBT run with at least one failure event)

406 failure events in 32 runs; total damage $2,314.0 vs total bound $6,179.5; damage/bound per run: min 0.304, median 0.352, max 0.655; bound held in every run: True.

| scenario | runs | events | damage | Σ bound | Σ a-priori (budget) bound |
|---|---|---|---|---|---|
| 2_always_lie | 5 | 120 | 622.0 | 1,680.0 | 4,680.0 |
| 3_farm_then_lie | 5 | 5 | 29.5 | 84.0 | 550.6 |
| 4_slow_drift | 5 | 99 | 481.0 | 1,386.0 | 4,407.0 |
| 8_claim_splitting | 2 | 28 | 140.0 | 420.0 | 1,170.0 |
| 9_noisy_honest | 5 | 19 | 322.0 | 649.5 | 1,716.0 |
| 10_farm_fail_refarm | 5 | 10 | 67.5 | 210.0 | 1,284.7 |
| 12_sybil_reentry | 5 | 125 | 652.0 | 1,750.0 | 4,875.0 |
