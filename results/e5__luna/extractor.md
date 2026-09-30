## Extractor accuracy

| extractor | split | n | precision | recall | exact | honest→UNTESTABLE |
|---|---|---|---|---|---|---|
| llm:gpt-5.6-luna | test | 199 | 1.0 | 0.9898 | 0.9849 | 0.0 |
| llm:gpt-5.6-luna:test_hard | test_hard | 30 | 1.0 | 1.0 | 1.0 | None |
| llm:gpt-5.6-luna:test_hard:no_guard | test_hard | 30 | 0.5882 | 1.0 | 0.3 | None |
| rule | test | 199 | 1.0 | 1.0 | 1.0 | 0.0 |
| rule:test_hard | test_hard | 30 | 1.0 | 1.0 | 1.0 | None |

## Hard-phrasing subset (shipping/ready/scheduled dates recorded as delivery deadlines)

| extractor | recorded | ship | ready | scheduled | PRICE recovered |
|---|---|---|---|---|---|
| llm:gpt-5.6-luna:test_hard | 0/30 | 0/12 | 0/9 | 0/9 | 1.0 |
| llm:gpt-5.6-luna:test_hard:no_guard | 21/30 | 12/12 | 9/9 | 0/9 | 1.0 |
| rule:test_hard | 0/30 | 0/12 | 0/9 | 0/9 | 1.0 |

## Scenario-11 injections

| extractor | injected recorded | accuracy vs F5 gold | n |
|---|---|---|---|
| llm:gpt-5.6-luna | 0 | 1.0 | 29 |
| rule | 0 | 1.0 | 29 |
