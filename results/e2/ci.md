Mean over seeds with a 95% CI (percentile bootstrap over the 3 seeds, 10,000 resamples; with 3 seeds the interval is coarse). $ per run.

## Attack loss per defense (loss from lies, mean of scenarios 2-12)

| defense | mean [95% CI] | per seed |
|---|---|---|
| obt | 43.1 [32.8, 56.3] | s1: 32.8, s2: 40.1, s3: 56.3 |
| none | 2,290.6 [2,127.5, 2,469.5] | s1: 2,127.5, s2: 2,469.5, s3: 2,274.6 |
| provenance | 1,649.9 [1,471.5, 1,903.2] | s1: 1,574.9, s2: 1,471.5, s3: 1,903.2 |
| llm_selfcheck | 740.8 [520.5, 934.1] | s1: 520.5, s2: 934.1, s3: 767.8 |
| rep-strict | 190.4 [122.0, 248.0] | s1: 201.1, s2: 248.0, s3: 122.0 |
| rep-default | 463.8 [368.7, 563.8] | s1: 563.8, s2: 459.1, s3: 368.7 |

## Utility cost per defense (primary utility metric: cost − cost(none), honest S_main, same seed)

| defense | utility cost, honest [95% CI] | utility cost, noisy-honest [95% CI] | S_main unit share, honest | S_main orders blocked, honest |
|---|---|---|---|---|
| obt | 298.3 [273.5, 329.5] | 328.5 [270.0, 381.0] | 0.054 | 0.3 |
| none | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.596 | 0.0 |
| provenance | 39.7 [26.0, 55.0] | 74.7 [54.0, 102.5] | 0.534 | 0.0 |
| llm_selfcheck | 75.3 [44.0, 99.0] | 125.8 [102.0, 172.5] | 0.475 | 7.3 |
| rep-strict | 291.5 [271.5, 308.0] | 326.3 [277.5, 355.0] | 0.070 | 2.0 |
| rep-default | 63.3 [-15.0, 106.0] | 292.7 [222.0, 355.0] | 0.512 | 2.0 |

## Utility cost as a % of the honest run's total cost (cost(none, honest), same seed)

| defense | honest [95% CI] | noisy-honest [95% CI] |
|---|---|---|
| obt | 4.97% [4.65, 5.51] | 5.49% [4.59, 6.42] |
| none | 0.00% [0.00, 0.00] | 0.00% [0.00, 0.00] |
| provenance | 0.66% [0.44, 0.92] | 1.25% [0.92, 1.73] |
| llm_selfcheck | 1.26% [0.74, 1.68] | 2.11% [1.68, 2.91] |
| rep-strict | 4.85% [4.61, 5.01] | 5.45% [4.72, 5.84] |
| rep-default | 1.04% [-0.25, 1.72] | 4.88% [3.78, 5.80] |

## Scenario 9 (noisy-honest) utility cost, every defense

Noisy-honest is an honest supplier with random delays: any cost above no defense is utility lost to false positives.

| defense | utility cost [95% CI] | S_main unit share | S_main orders blocked |
|---|---|---|---|
| obt | 328.5 [270.0, 381.0] | 0.051 | 0.3 |
| none | 0.0 [0.0, 0.0] | 0.630 | 0.0 |
| provenance | 74.7 [54.0, 102.5] | 0.493 | 0.0 |
| llm_selfcheck | 125.8 [102.0, 172.5] | 0.395 | 8.0 |
| rep-strict | 326.3 [277.5, 355.0] | 0.054 | 16.7 |
| rep-default | 292.7 [222.0, 355.0] | 0.105 | 16.7 |

## Loss from lies per scenario (mean [95% CI] over seeds)

| scenario | obt | none | provenance | llm_selfcheck | rep-strict | rep-default |
|---|---|---|---|---|---|---|
| 1_honest | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| 2_always_lie | 122.2 [107.0, 135.5] | 7,107.3 [6,865.5, 7,268.0] | 5,562.3 [4,101.0, 7,270.0] | 1,944.5 [1,223.5, 2,332.5] | 290.7 [107.5, 384.0] | 518.8 [309.5, 667.0] |
| 3_farm_then_lie | 2.3 [-1.2, 5.0] | 57.7 [32.0, 100.8] | 99.0 [57.2, 128.8] | 96.0 [-4.0, 205.5] | 0.0 [0.0, 0.0] | 54.4 [-36.5, 143.5] |
| 4_slow_drift | 86.0 [71.0, 105.0] | 1,778.8 [1,391.0, 2,118.0] | 1,103.3 [990.5, 1,272.0] | 456.8 [316.0, 609.5] | 0.0 [0.0, 0.0] | 191.7 [153.0, 248.5] |
| 5_price_bait | -19.7 [-24.0, -11.0] | 808.7 [754.5, 860.0] | 691.0 [609.5, 743.0] | 650.0 [580.5, 747.0] | 108.0 [71.5, 144.0] | 794.0 [677.5, 977.5] |
| 6_vague | 37.2 [24.5, 50.0] | 611.7 [468.5, 777.0] | 647.5 [506.0, 823.5] | 272.8 [217.0, 342.5] | 93.8 [46.5, 179.5] | 322.0 [257.5, 375.5] |
| 7_far_deadlines | 37.3 [24.5, 50.0] | 5,627.8 [5,529.0, 5,776.0] | 4,480.9 [4,124.2, 4,725.0] | 1,452.6 [1,025.2, 2,264.8] | 431.8 [355.8, 571.0] | 659.9 [557.8, 767.0] |
| 8_claim_splitting | 37.8 [12.5, 80.0] | 632.7 [414.5, 893.5] | 446.8 [341.5, 628.5] | 337.5 [221.0, 552.5] | 7.2 [-6.5, 34.5] | 687.8 [580.0, 866.5] |
| 9_noisy_honest | 1.0 [-9.5, 12.5] | -29.2 [-51.5, -6.0] | 5.8 [-4.0, 22.0] | 21.3 [-10.0, 77.0] | 5.7 [0.0, 17.0] | 200.2 [150.5, 231.0] |
| 10_farm_fail_refarm | 5.3 [4.0, 7.0] | 193.4 [160.2, 253.0] | 236.1 [218.2, 261.5] | 172.7 [9.5, 354.0] | 0.0 [0.0, 0.0] | 60.0 [-54.0, 278.5] |
| 11_extraction_attack | 36.7 [24.0, 49.5] | 706.8 [330.2, 1,373.5] | 726.3 [383.2, 1,111.0] | 260.2 [199.0, 322.5] | 212.2 [84.0, 379.5] | 440.3 [286.0, 575.5] |
| 12_sybil_reentry | 127.5 [112.0, 138.5] | 7,700.5 [6,233.5, 9,425.0] | 4,149.5 [3,140.5, 5,074.5] | 2,484.3 [1,596.5, 3,005.5] | 945.0 [657.0, 1,142.0] | 1,173.2 [859.0, 1,428.5] |

## OBT damage vs bound (every OBT run with at least one failure event)

239 failure events in 19 runs; total damage $1,364.0 vs total bound $3,652.5; damage/bound per run: min 0.304, median 0.352, max 0.655; bound held in every run: True.

| scenario | runs | events | damage | Σ bound | Σ a-priori (budget) bound |
|---|---|---|---|---|---|
| 2_always_lie | 3 | 72 | 372.5 | 1,008.0 | 2,808.0 |
| 3_farm_then_lie | 3 | 3 | 18.0 | 56.0 | 321.2 |
| 4_slow_drift | 3 | 59 | 283.5 | 826.0 | 2,613.0 |
| 8_claim_splitting | 1 | 14 | 70.0 | 210.0 | 585.0 |
| 9_noisy_honest | 3 | 10 | 181.5 | 362.5 | 897.0 |
| 10_farm_fail_refarm | 3 | 6 | 45.0 | 140.0 | 780.0 |
| 12_sybil_reentry | 3 | 75 | 393.5 | 1,050.0 | 2,925.0 |
