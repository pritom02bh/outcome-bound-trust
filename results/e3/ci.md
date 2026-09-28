Mean over seeds with a 95% CI (percentile bootstrap over seeds, 10,000 resamples). Seeds per row are given in the `seeds` column: a defense can have more seeds than another (extra seeds were run for some), and a utility cost needs the `none` run on the same seed. With few seeds the interval is coarse. $ per run.

## Attack loss per defense (loss from lies, mean of scenarios 2-12)

| defense | seeds | mean [95% CI] | per seed |
|---|---|---|---|
| obt | 1 | 3,189.1 [3,189.1, 3,189.1] | s1: 3,189.1 |
| none | 1 | 6,934.0 [6,934.0, 6,934.0] | s1: 6,934.0 |

## Utility cost per defense (primary utility metric: cost − cost(none), honest S_main, same seed)

| defense | seeds | utility cost, honest [95% CI] | utility cost, noisy-honest [95% CI] | S_main unit share, honest | S_main orders blocked, honest |
|---|---|---|---|---|---|
| obt | 1 | -82.5 [-82.5, -82.5] | 12.0 [12.0, 12.0] | 0.292 | 25.0 |
| none | 1 | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.481 | 0.0 |

## Utility cost as a % of the honest run's total cost (cost(none, honest), same seed)

| defense | honest [95% CI] | noisy-honest [95% CI] |
|---|---|---|
| obt | -1.30% [-1.30, -1.30] | 0.19% [0.19, 0.19] |
| none | 0.00% [0.00, 0.00] | 0.00% [0.00, 0.00] |

## Scenario 9 (noisy-honest) utility cost, every defense

Noisy-honest is an honest supplier with random delays: any cost above no defense is utility lost to false positives.

| defense | utility cost [95% CI] | S_main unit share | S_main orders blocked |
|---|---|---|---|
| obt | 12.0 [12.0, 12.0] | 0.097 | 23.0 |
| none | 0.0 [0.0, 0.0] | 0.481 | 0.0 |

## Loss from lies per scenario (mean [95% CI] over each defense's seeds, as above)

| scenario | obt | none |
|---|---|---|
| 1_honest | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| 2_always_lie | 2,284.5 [2,284.5, 2,284.5] | 15,354.0 [15,354.0, 15,354.0] |
| 3_farm_then_lie | 98.0 [98.0, 98.0] | 303.0 [303.0, 303.0] |
| 4_slow_drift | 186.5 [186.5, 186.5] | 681.5 [681.5, 681.5] |
| 5_price_bait | 9,551.0 [9,551.0, 9,551.0] | 614.0 [614.0, 614.0] |
| 6_vague | 11,901.5 [11,901.5, 11,901.5] | 3,552.0 [3,552.0, 3,552.0] |
| 7_far_deadlines | 1,038.0 [1,038.0, 1,038.0] | 15,060.0 [15,060.0, 15,060.0] |
| 8_claim_splitting | 2,358.0 [2,358.0, 2,358.0] | 8,334.5 [8,334.5, 8,334.5] |
| 9_noisy_honest | 118.5 [118.5, 118.5] | 24.0 [24.0, 24.0] |
| 10_farm_fail_refarm | 150.2 [150.2, 150.2] | 513.5 [513.5, 513.5] |
| 11_extraction_attack | 3,187.0 [3,187.0, 3,187.0] | 16,483.0 [16,483.0, 16,483.0] |
| 12_sybil_reentry | 4,207.0 [4,207.0, 4,207.0] | 15,354.0 [15,354.0, 15,354.0] |

## OBT damage vs bound (every OBT run with at least one failure event)

48 failure events in 6 runs; total damage $457.0 vs total bound $1,271.5; damage/bound per run: min 0.321, median 0.329, max 0.468; bound held in every run: True.

| scenario | runs | events | damage | Σ bound | Σ a-priori (budget) bound |
|---|---|---|---|---|---|
| 2_always_lie | 1 | 5 | 23.0 | 70.0 | 195.0 |
| 3_farm_then_lie | 1 | 1 | 54.0 | 168.0 | 550.6 |
| 4_slow_drift | 1 | 17 | 81.5 | 238.0 | 819.0 |
| 9_noisy_honest | 1 | 2 | 136.5 | 291.5 | 390.0 |
| 10_farm_fail_refarm | 1 | 2 | 67.5 | 210.0 | 688.2 |
| 12_sybil_reentry | 1 | 21 | 94.5 | 294.0 | 819.0 |
