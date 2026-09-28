Mean over seeds with a 95% CI (percentile bootstrap over the 1 seeds, 10,000 resamples; with 1 seeds the interval is coarse). $ per run.

## Attack loss per defense (loss from lies, mean of scenarios 2-12)

| defense | mean [95% CI] | per seed |
|---|---|---|
| obt | 1,191.2 [1,191.2, 1,191.2] | s1: 1,191.2 |

## Utility cost per defense (primary utility metric: cost − cost(none), honest S_main, same seed)

| defense | utility cost, honest [95% CI] | utility cost, noisy-honest [95% CI] | S_main unit share, honest | S_main orders blocked, honest |
|---|---|---|---|---|
| obt | - | - | 0.292 | 25.0 |

## Utility cost as a % of the honest run's total cost (cost(none, honest), same seed)

| defense | honest [95% CI] | noisy-honest [95% CI] |
|---|---|---|
| obt | - | - |

## Scenario 9 (noisy-honest) utility cost, every defense

Noisy-honest is an honest supplier with random delays: any cost above no defense is utility lost to false positives.

| defense | utility cost [95% CI] | S_main unit share | S_main orders blocked |
|---|---|---|---|
| obt | - | - | - |

## Loss from lies per scenario (mean [95% CI] over seeds)

| scenario | obt |
|---|---|
| 1_honest | 0.0 [0.0, 0.0] |
| 2_always_lie | 2,284.5 [2,284.5, 2,284.5] |
| 3_farm_then_lie | 98.0 [98.0, 98.0] |

## OBT damage vs bound (every OBT run with at least one failure event)

6 failure events in 2 runs; total damage $77.0 vs total bound $238.0; damage/bound per run: min 0.321, median 0.329, max 0.329; bound held in every run: True.

| scenario | runs | events | damage | Σ bound | Σ a-priori (budget) bound |
|---|---|---|---|---|---|
| 2_always_lie | 1 | 5 | 23.0 | 70.0 | 195.0 |
| 3_farm_then_lie | 1 | 1 | 54.0 | 168.0 | 550.6 |
