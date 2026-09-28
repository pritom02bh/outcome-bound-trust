## E2b: trust-aware buyer view (supplementary; E2 is the main result)

gpt-oss buyer with the frozen trust-aware view (D30); scenarios 1_honest, 2_always_lie, 3_farm_then_lie, 9_noisy_honest, 12_sybil_reentry; seeds [1, 2, 3]. Mean [95% bootstrap CI over seeds]. The E2 column is the same defense, scenarios and seeds with the standard view. Utility cost is against E2's honest `none` run on the same seed.

### obt

| metric | E2b trust-aware | E2 standard view |
|---|---|---|
| S_main unit share, honest | 0.068 | 0.054 |
| utility cost, honest ($) | 291.2 [273.5, 319.5] | 298.3 [273.5, 329.5] |
| loss from lies, 2_always_lie ($) | 129.2 [102.5, 151.0] | 122.2 [107.0, 135.5] |
| loss from lies, 3_farm_then_lie ($) | -10.2 [-15.2, -2.2] | 2.3 [-1.2, 5.0] |
| loss from lies, 9_noisy_honest ($) | 0.7 [-20.0, 21.5] | 1.0 [-9.5, 12.5] |
| loss from lies, 12_sybil_reentry ($) | 136.0 [112.0, 154.0] | 127.5 [112.0, 138.5] |

### rep-strict

| metric | E2b trust-aware | E2 standard view |
|---|---|---|
| S_main unit share, honest | 0.071 | 0.070 |
| utility cost, honest ($) | 290.8 [258.5, 332.0] | 291.5 [271.5, 308.0] |
| loss from lies, 2_always_lie ($) | 360.5 [324.5, 431.0] | 290.7 [107.5, 384.0] |
| loss from lies, 3_farm_then_lie ($) | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |
| loss from lies, 9_noisy_honest ($) | 4.7 [0.0, 14.0] | 5.7 [0.0, 17.0] |
| loss from lies, 12_sybil_reentry ($) | 769.0 [579.5, 881.0] | 945.0 [657.0, 1,142.0] |

OBT damage vs bound, E2b: 160 failure events in 12 runs; damage $999.0 vs bound $2,546.0; max per-run ratio 0.638; bound held in every run: True.
OBT damage vs bound, E2, same scenarios and seeds: 160 failure events in 12 runs; damage $965.5 vs bound $2,476.5; max per-run ratio 0.655; bound held in every run: True.
