## Semantic reader (message bank v3)

| check | n | correct | deadline question |
|---|---|---|---|
| checker_holdout_run1 | 20 | 18 | 20 |
| checker_holdout_run2 | 20 | 20 | 20 |
| checker_validation_fewshot1 | 20 | 18 | - |
| checker_validation_fewshot2 | 20 | 18 | - |
| checker_validation_fewshot3 | 20 | 19 | - |
| checker_validation_fewshot3_think | 20 | 20 | - |
| checker_validation_fewshot4_q | 20 | 18 | - |
| checker_validation_fewshot5_think | 20 | 20 | - |
| checker_validation_zero_shot | 20 | 11 | - |

## Extractor dev tuning (dev split only)

| pass | precision | recall | exact | honest→UNTESTABLE | errors |
|---|---|---|---|---|---|
| v3_guard_dev | 1.0 | 1.0 | 1.0 | 0.0 | 0 |
| v3_pass1 | 1.0 | 0.9189 | 0.88 | 0.1091 | 6 |
| v3_pass2 | 1.0 | 0.9865 | 0.98 | 0.0182 | 1 |
