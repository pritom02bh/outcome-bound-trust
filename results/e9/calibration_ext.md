# E9 calibration, extended OBT grid (D45a)

Same rule as D45. If the pick is again on a grid edge, that is reported, not extended further.

## e9_calibration_ext

E9 OBT calibration on the extended grid (D45a: b0 2.5-80% of per-round spend x k 1, 2, 4), same rule as D45, next to the transferred config and D45's pick. Seeds 1-3, mean [95% bootstrap CI over seeds]; $ per run. Pick moved: no; pick on a grid edge: k min.

| defense | setting | config | loss from lies | damage | reroute premium | resid | utility cost | utility (% of cost) | provider share |
|---|---|---|---|---|---|---|---|---|---|
| obt | transferred | obt_b0.05_k1 (b0_frac 0.05, budget_k 1) | 42.6 [34.8, 53.2] | 20.3 | 19.6 | 2.7 | 327.3 [310.0, 346.0] | 22.57 | 0.111 |
| obt | calibrated, D45 grid | obt_b0.2_k1 (b0_frac 0.2, budget_k 1) | 46.3 [40.8, 50.0] | 68.7 | 35.4 | -57.8 | 293.7 [269.0, 323.0] | 20.25 | 0.222 |
| obt | calibrated, extended grid | obt_b0.2_k1 (b0_frac 0.2, budget_k 1) | 46.3 [40.8, 50.0] | 68.7 | 35.4 | -57.8 | 293.7 [269.0, 323.0] | 20.25 | 0.222 |

## e9_calibration_ext_bound

E9 extended OBT grid (D45a): the loss bound over every run (18 points x 7 scenarios x 3 seeds).

| OBT runs | failure events | max damage/bound | held | invariant violations | pick moved | pick on grid edge |
|---|---|---|---|---|---|---|
| 378 | 1500 | 1.000 | yes | 0 | no | k min |

## e9_calibration_ext_grid

E9 extended OBT grid (D45a): every point, scripted buyer, seeds 1-3, $ per run. Max damage/bound over the point's runs.

| point | b0 | k | utility cost | loss from lies | never trades | front | chosen | new in D45a | max damage/bound |
|---|---|---|---|---|---|---|---|---|---|
| obt_b0.025_k1 | 0.025 | 1 | 413.7 | 0.0 | yes |  |  |  | - |
| obt_b0.025_k2 | 0.025 | 2 | 413.7 | 0.0 | yes |  |  |  | - |
| obt_b0.025_k4 | 0.025 | 4 | 413.7 | 0.0 | yes |  |  | yes | - |
| obt_b0.05_k1 | 0.05 | 1 | 327.3 | 42.6 |  | yes |  |  | 1.000 |
| obt_b0.05_k2 | 0.05 | 2 | 303.7 | 57.8 |  |  |  |  | 0.423 |
| obt_b0.05_k4 | 0.05 | 4 | 254.7 | 112.7 |  |  |  | yes | 0.815 |
| obt_b0.1_k1 | 0.1 | 1 | 284.7 | 67.7 |  | yes |  |  | 1.000 |
| obt_b0.1_k2 | 0.1 | 2 | 246.7 | 110.3 |  | yes |  |  | 0.550 |
| obt_b0.1_k4 | 0.1 | 4 | 248.7 | 112.1 |  |  |  | yes | 0.815 |
| obt_b0.2_k1 | 0.2 | 1 | 293.7 | 46.3 |  | yes | yes |  | 0.411 |
| obt_b0.2_k2 | 0.2 | 2 | 244.7 | 110.5 |  | yes |  |  | 0.815 |
| obt_b0.2_k4 | 0.2 | 4 | 251.3 | 116.0 |  |  |  | yes | 0.815 |
| obt_b0.4_k1 | 0.4 | 1 | 247.3 | 146.1 |  |  |  | yes | 0.792 |
| obt_b0.4_k2 | 0.4 | 2 | 186.3 | 187.7 |  | yes |  | yes | 0.860 |
| obt_b0.4_k4 | 0.4 | 4 | 186.3 | 188.7 |  |  |  | yes | 0.860 |
| obt_b0.8_k1 | 0.8 | 1 | 183.0 | 275.9 |  | yes |  | yes | 0.898 |
| obt_b0.8_k2 | 0.8 | 2 | 183.0 | 275.9 |  | yes |  | yes | 0.898 |
| obt_b0.8_k4 | 0.8 | 4 | 183.0 | 277.6 |  |  |  | yes | 0.898 |

OBT front (extended grid): obt_b0.8_k1, obt_b0.8_k2, obt_b0.4_k2, obt_b0.2_k2, obt_b0.1_k2, obt_b0.1_k1, obt_b0.2_k1, obt_b0.05_k1.
