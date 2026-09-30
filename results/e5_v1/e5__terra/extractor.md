## Extractor accuracy

| extractor | split | n | precision | recall | exact | honest→UNTESTABLE |
|---|---|---|---|---|---|---|
| llm:gpt-5.6-terra | test | 199 | 1.0 | 1.0 | 1.0 | 0.0 |
| llm:gpt-5.6-terra:test_hard | test_hard | 30 | 1.0 | 0.9333 | 0.9333 | None |
| llm:gpt-5.6-terra:test_hard:no_guard | test_hard | 30 | 0.6087 | 0.9333 | 0.3333 | None |
| rule | test | 199 | 1.0 | 1.0 | 1.0 | 0.0 |
| rule:test_hard | test_hard | 30 | 1.0 | 1.0 | 1.0 | None |

## Hard-phrasing subset (shipping/ready/scheduled dates recorded as delivery deadlines)

| extractor | recorded | ship | ready | scheduled | PRICE recovered |
|---|---|---|---|---|---|
| llm:gpt-5.6-terra:test_hard | 0/30 | 0/12 | 0/9 | 0/9 | 0.9333 |
| llm:gpt-5.6-terra:test_hard:no_guard | 18/30 | 10/12 | 8/9 | 0/9 | 0.9333 |
| rule:test_hard | 0/30 | 0/12 | 0/9 | 0/9 | 1.0 |

## Scenario-11 injections

| extractor | injected recorded | accuracy vs F5 gold | n |
|---|---|---|---|
| llm:gpt-5.6-terra | 0 | 1.0 | 29 |
| rule | 0 | 1.0 | 29 |
