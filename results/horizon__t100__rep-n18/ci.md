Mean over seeds with a 95% CI (percentile bootstrap over seeds, 10,000 resamples). Seeds per row are given in the `seeds` column: a defense can have more seeds than another (extra seeds were run for some), and a utility cost needs the `none` run on the same seed. With few seeds the interval is coarse. $ per run.

## Attack loss per defense (loss from lies, mean of scenarios 2-12)

| defense | seeds | mean [95% CI] | per seed |
|---|---|---|---|
| reputation | 3 | 1,170.3 [1,153.1, 1,189.6] | s1: 1,153.1, s2: 1,168.3, s3: 1,189.6 |

## Utility cost per defense (primary utility metric: cost − cost(none), honest S_main, same seed)

| defense | seeds | utility cost, honest [95% CI] | utility cost, noisy-honest [95% CI] | S_main unit share, honest | S_main orders blocked, honest |
|---|---|---|---|---|---|
| reputation | 0 | - | - | 0.919 | 0.0 |

## Utility cost as a % of the honest run's total cost (cost(none, honest), same seed)

| defense | honest [95% CI] | noisy-honest [95% CI] |
|---|---|---|
| reputation | - | - |

## Scenario 9 (noisy-honest) utility cost, every defense

Noisy-honest is an honest supplier with random delays: any cost above no defense is utility lost to false positives.

| defense | utility cost [95% CI] | S_main unit share | S_main orders blocked |
|---|---|---|---|
| reputation | - | 0.348 | 62.7 |

## Loss from lies per scenario (mean [95% CI] over each defense's seeds, as above)

| scenario | reputation |
|---|---|
| 1_honest | 0.0 [0.0, 0.0] |
| 2_always_lie | 1,367.3 [1,308.5, 1,467.0] |
| 3_farm_then_lie | 55.7 [51.5, 61.8] |
| 4_slow_drift | 861.0 [826.5, 905.5] |
| 5_price_bait | 2,725.5 [2,707.5, 2,746.5] |
| 6_vague | 1,093.8 [1,021.0, 1,189.0] |
| 7_far_deadlines | 1,356.2 [1,296.0, 1,456.0] |
| 8_claim_splitting | 1,377.0 [1,222.0, 1,563.5] |
| 9_noisy_honest | 560.5 [169.5, 768.0] |
| 10_farm_fail_refarm | 132.1 [104.8, 175.2] |
| 11_extraction_attack | 1,127.2 [1,064.0, 1,228.8] |
| 12_sybil_reentry | 2,217.5 [2,072.0, 2,392.0] |

## OBT damage vs bound (every OBT run with at least one failure event)

0 failure events in 0 runs; total damage $0.0 vs total bound $0.0; damage/bound per run: min None, median None, max None; bound held in every run: True.

| scenario | runs | events | damage | Σ bound | Σ a-priori (budget) bound |
|---|---|---|---|---|---|
