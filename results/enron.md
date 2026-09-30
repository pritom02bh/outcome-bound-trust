## Enron real-text check (D34, D38): frozen extractors on 100 labeled real sentences

Labels: `data/enron_candidates.csv` (drafted with LLM assistance, verified row by row by the author). Per stratum, never pooled. Target for wrong claims recorded: 0.

| extractor | stratum | rows | commitments | labeled claims | claims UNTESTABLE | recorded | wrong recorded | recorded from non-commitments |
|---|---|---|---|---|---|---|---|---|
| llm:gpt-oss:20b | delivery | 50 | 1 | 1 | 1 | 0 | 0 | 0 |
| llm:gpt-oss:20b | price | 50 | 9 | 9 | 9 | 0 | 0 | 0 |
| rule | delivery | 50 | 1 | 1 | 1 | 0 | 0 | 0 |
| rule | price | 50 | 9 | 9 | 9 | 0 | 0 | 0 |
