Mean over seeds with a 95% CI (percentile bootstrap over seeds, 10,000 resamples). Seeds per row are given in the `seeds` column: a defense can have more seeds than another (extra seeds were run for some), and a utility cost needs the `none` run on the same seed. With few seeds the interval is coarse. $ per run.

## Attack loss per defense (loss from lies, mean of scenarios 2-12)

| defense | seeds | mean [95% CI] | per seed |
|---|---|---|---|
| obt | 3 | 63.9 [48.1, 77.8] | s1: 48.1, s2: 65.8, s3: 77.8 |
| rep-strict | 3 | 283.5 [226.4, 319.4] | s1: 226.4, s2: 319.4, s3: 304.9 |

## Utility cost per defense (primary utility metric: cost − cost(none), honest S_main, same seed)

| defense | seeds | utility cost, honest [95% CI] | utility cost, noisy-honest [95% CI] | S_main unit share, honest | S_main orders blocked, honest |
|---|---|---|---|---|---|
| obt | 0 | - | - | 0.068 | 1.0 |
| rep-strict | 0 | - | - | 0.071 | 0.0 |

## Utility cost as a % of the honest run's total cost (cost(none, honest), same seed)

| defense | honest [95% CI] | noisy-honest [95% CI] |
|---|---|---|
| obt | - | - |
| rep-strict | - | - |

## Scenario 9 (noisy-honest) utility cost, every defense

Noisy-honest is an honest supplier with random delays: any cost above no defense is utility lost to false positives.

| defense | utility cost [95% CI] | S_main unit share | S_main orders blocked |
|---|---|---|---|
| obt | - | 0.060 | 0.0 |
| rep-strict | - | 0.070 | 0.7 |

## Loss from lies per scenario (mean [95% CI] over each defense's seeds, as above)

| scenario | obt | rep-strict |
|---|---|---|
| 1_honest | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| 2_always_lie | 129.2 [102.5, 151.0] | 360.5 [324.5, 431.0] |
| 3_farm_then_lie | -10.2 [-15.2, -2.2] | 0.0 [0.0, 0.0] |
| 9_noisy_honest | 0.7 [-20.0, 21.5] | 4.7 [0.0, 14.0] |
| 12_sybil_reentry | 136.0 [112.0, 154.0] | 769.0 [579.5, 881.0] |

## OBT damage vs bound (every OBT run with at least one failure event)

160 failure events in 12 runs; total damage $999.0 vs total bound $2,546.0; damage/bound per run: min 0.321, median 0.375, max 0.638; bound held in every run: True.

| scenario | runs | events | damage | Σ bound | Σ a-priori (budget) bound |
|---|---|---|---|---|---|
| 2_always_lie | 3 | 72 | 367.5 | 1,008.0 | 2,808.0 |
| 3_farm_then_lie | 3 | 3 | 13.5 | 42.0 | 412.9 |
| 9_noisy_honest | 3 | 10 | 224.0 | 446.0 | 1,053.0 |
| 12_sybil_reentry | 3 | 75 | 394.0 | 1,050.0 | 2,925.0 |
