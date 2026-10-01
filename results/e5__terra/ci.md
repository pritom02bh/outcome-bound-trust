Mean over seeds with a 95% CI (percentile bootstrap over seeds, 10,000 resamples). Seeds per row are given in the `seeds` column: a defense can have more seeds than another (extra seeds were run for some), and a utility cost needs the `none` run on the same seed. With few seeds the interval is coarse. $ per run.

## Attack loss per defense (loss from lies, mean of scenarios 2-12)

| defense | seeds | mean [95% CI] | per seed |
|---|---|---|---|
| none | 3 | 1,177.2 [942.2, 1,575.1] | s1: 942.2, s2: 1,575.1, s3: 1,014.3 |
| obt+planner | 3 | 176.2 [158.0, 189.5] | s1: 158.0, s2: 181.3, s3: 189.5 |

## Utility cost per defense (primary utility metric: cost − cost(none), honest S_main, same seed)

| defense | seeds | utility cost, honest [95% CI] | utility cost, noisy-honest [95% CI] | S_main unit share, honest | S_main orders blocked, honest |
|---|---|---|---|---|---|
| none | 3 | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.935 | 0.0 |
| obt+planner | 3 | 335.8 [312.0, 364.5] | 442.8 [409.5, 508.0] | 0.293 | 0.0 |

## Utility cost as a % of the honest run's total cost (cost(none, honest), same seed)

| defense | honest [95% CI] | noisy-honest [95% CI] |
|---|---|---|
| none | 0.00% [0.00, 0.00] | 0.00% [0.00, 0.00] |
| obt+planner | 5.75% [5.46, 6.11] | 7.62% [7.07, 8.60] |

## Scenario 9 (noisy-honest) utility cost, every defense

Noisy-honest is an honest supplier with random delays: any cost above no defense is utility lost to false positives.

| defense | utility cost [95% CI] | S_main unit share | S_main orders blocked |
|---|---|---|---|
| none | 0.0 [0.0, 0.0] | 0.927 | 0.0 |
| obt+planner | 442.8 [409.5, 508.0] | 0.151 | 0.0 |

## Loss from lies per scenario (mean [95% CI] over each defense's seeds, as above)

| scenario | none | obt+planner |
|---|---|---|
| 1_honest | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| 2_always_lie | 2,494.3 [1,146.5, 4,693.5] | 252.7 [236.0, 267.0] |
| 3_farm_then_lie | 12.0 [-72.5, 59.2] | 162.8 [103.8, 224.8] |
| 4_slow_drift | 2,404.2 [2,005.5, 2,637.5] | 214.8 [206.0, 231.5] |
| 5_price_bait | 1,442.0 [1,406.0, 1,472.5] | 138.2 [128.5, 147.0] |
| 6_vague | 890.5 [759.0, 1,070.5] | 167.8 [154.0, 180.0] |
| 7_far_deadlines | 1,618.5 [1,136.5, 2,392.0] | 167.8 [154.0, 180.0] |
| 8_claim_splitting | 978.5 [751.5, 1,316.0] | 157.8 [149.0, 164.5] |
| 9_noisy_honest | -35.8 [-52.0, -24.5] | 71.2 [55.5, 91.5] |
| 10_farm_fail_refarm | 188.1 [103.8, 300.2] | 178.8 [145.0, 208.0] |
| 11_extraction_attack | 1,367.2 [734.8, 2,262.0] | 167.3 [153.5, 179.5] |
| 12_sybil_reentry | 1,590.0 [1,275.5, 1,804.5] | 259.5 [241.5, 275.0] |

## OBT damage vs bound (every OBT run with at least one failure event)

0 failure events in 0 runs; total damage $0.0 vs total bound $0.0; damage/bound per run: min None, median None, max None; bound held in every run: True.

| scenario | runs | events | damage | Σ bound | Σ a-priori (budget) bound |
|---|---|---|---|---|---|
