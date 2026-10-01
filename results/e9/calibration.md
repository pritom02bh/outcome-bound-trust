# E9 calibration: transferred vs calibrated configs (D45)

Rule (fixed in E1, D22, with D33's never-trade exclusion): per defense, the Pareto front in (utility cost, attack loss) over its non-degenerate grid points; pick the front point with the smallest sum.

## e9_calibration

E9 with transferred vs calibrated configs (D45). Transferred: the supply-domain configs E9 ran with (D44). Calibrated: each defense's cloud-domain grid point chosen by E1's rule (Pareto front in utility cost and attack loss, smallest sum; never-trading points excluded). Seeds 1-3, mean [95% bootstrap CI over seeds]; $ per run.

| defense | setting | config | loss from lies | damage | reroute premium | resid | utility cost | utility (% of cost) | provider share |
|---|---|---|---|---|---|---|---|---|---|
| obt | transferred | obt_b0.05_k1 (b0_frac 0.05, budget_k 1) | 42.6 [34.8, 53.2] | 20.3 | 19.6 | 2.7 | 327.3 [310.0, 346.0] | 22.57 | 0.111 |
| obt | calibrated | obt_b0.2_k1 (b0_frac 0.2, budget_k 1) | 46.3 [40.8, 50.0] | 68.7 | 35.4 | -57.8 | 293.7 [269.0, 323.0] | 20.25 | 0.222 |
| rep-strict | transferred | rep_n3_th0.9_cap200 (rep_n0 3, rep_theta 0.9, rep_cap 200.0) | 134.9 [116.0, 145.0] | n/a | 0.0 | 134.9 | 266.0 [240.0, 304.0] | 18.34 | 0.193 |
| rep-strict | calibrated | rep_n8_th0.8_cap200 (rep_n0 8, rep_theta 0.8, rep_cap 200.0) | 371.0 [340.8, 387.0] | n/a | 0.0 | 371.0 | 0.0 [0.0, 0.0] | 0.00 | 0.974 |

## e9_calibration_bound

E9 calibration (D45): the loss bound over every OBT grid run (8 points x 7 scenarios x 3 seeds), and the harness check that the transferred grid points reproduce E9's runs.

| OBT runs | failure events | max damage/bound | held | invariant violations | transferred points reproduce E9 |
|---|---|---|---|---|---|
| 168 | 586 | 1.000 | yes | 0 | yes |

## e9_calibration_grid

E9 calibration grids (D45): every point, scripted buyer, seeds 1-3, $ per run. OBT over b0 (fraction of per-round spend) and k; reputation over n0, theta and cap (the D33 grid). Max damage/bound over the point's OBT runs.

| defense | point | utility cost | loss from lies | never trades | locks out | front | chosen | transferred | max damage/bound |
|---|---|---|---|---|---|---|---|---|---|
| obt | obt_b0.025_k1 | 413.7 | 0.0 | yes |  |  |  |  | - |
| obt | obt_b0.025_k2 | 413.7 | 0.0 | yes |  |  |  |  | - |
| obt | obt_b0.05_k1 | 327.3 | 42.6 |  |  | yes |  | yes | 1.000 |
| obt | obt_b0.05_k2 | 303.7 | 57.8 |  |  |  |  |  | 0.423 |
| obt | obt_b0.1_k1 | 284.7 | 67.7 |  |  | yes |  |  | 1.000 |
| obt | obt_b0.1_k2 | 246.7 | 110.3 |  |  | yes |  |  | 0.550 |
| obt | obt_b0.2_k1 | 293.7 | 46.3 |  |  | yes | yes |  | 0.411 |
| obt | obt_b0.2_k2 | 244.7 | 110.5 |  |  | yes |  |  | 0.815 |
| rep-strict | rep_n3_th0.8_cap100 | 413.7 | 0.0 | yes |  |  |  |  | - |
| rep-strict | rep_n3_th0.8_cap200 | 0.0 | 405.8 |  |  |  |  |  | - |
| rep-strict | rep_n3_th0.8_cap400 | 0.0 | 482.0 |  |  |  |  |  | - |
| rep-strict | rep_n3_th0.85_cap100 | 413.7 | 0.0 | yes |  |  |  |  | - |
| rep-strict | rep_n3_th0.85_cap200 | 266.0 | 134.9 |  | yes | yes |  |  | - |
| rep-strict | rep_n3_th0.85_cap400 | 266.0 | 211.1 |  | yes |  |  |  | - |
| rep-strict | rep_n3_th0.9_cap100 | 413.7 | 0.0 | yes |  |  |  |  | - |
| rep-strict | rep_n3_th0.9_cap200 | 266.0 | 134.9 |  | yes | yes |  | yes | - |
| rep-strict | rep_n3_th0.9_cap400 | 266.0 | 211.1 |  | yes |  |  |  | - |
| rep-strict | rep_n8_th0.8_cap100 | 413.7 | 0.0 | yes |  |  |  |  | - |
| rep-strict | rep_n8_th0.8_cap200 | 0.0 | 371.0 |  |  | yes | yes |  | - |
| rep-strict | rep_n8_th0.8_cap400 | 0.0 | 475.4 |  |  |  |  |  | - |
| rep-strict | rep_n8_th0.85_cap100 | 413.7 | 0.0 | yes |  |  |  |  | - |
| rep-strict | rep_n8_th0.85_cap200 | 0.0 | 384.7 |  |  |  |  |  | - |
| rep-strict | rep_n8_th0.85_cap400 | 0.0 | 489.1 |  |  |  |  |  | - |
| rep-strict | rep_n8_th0.9_cap100 | 413.7 | 0.0 | yes |  |  |  |  | - |
| rep-strict | rep_n8_th0.9_cap200 | 0.0 | 384.7 |  |  |  |  |  | - |
| rep-strict | rep_n8_th0.9_cap400 | 0.0 | 489.1 |  |  |  |  |  | - |
| rep-strict | rep_n18_th0.8_cap100 | 413.7 | 0.0 | yes |  |  |  |  | - |
| rep-strict | rep_n18_th0.8_cap200 | 0.0 | 476.8 |  |  |  |  |  | - |
| rep-strict | rep_n18_th0.8_cap400 | 0.0 | 641.2 |  |  |  |  |  | - |
| rep-strict | rep_n18_th0.85_cap100 | 413.7 | 0.0 | yes |  |  |  |  | - |
| rep-strict | rep_n18_th0.85_cap200 | 0.0 | 476.8 |  |  |  |  |  | - |
| rep-strict | rep_n18_th0.85_cap400 | 0.0 | 641.2 |  |  |  |  |  | - |
| rep-strict | rep_n18_th0.9_cap100 | 413.7 | 0.0 | yes |  |  |  |  | - |
| rep-strict | rep_n18_th0.9_cap200 | 0.0 | 477.2 |  |  |  |  |  | - |
| rep-strict | rep_n18_th0.9_cap400 | 0.0 | 641.6 |  |  |  |  |  | - |

OBT front: obt_b0.2_k2, obt_b0.1_k2, obt_b0.1_k1, obt_b0.2_k1, obt_b0.05_k1.

Reputation front (never-trading points excluded): rep_n8_th0.8_cap200, rep_n3_th0.85_cap200, rep_n3_th0.9_cap200.
