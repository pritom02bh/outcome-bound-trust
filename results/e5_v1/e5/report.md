# E5: paid buyers (GPT-5.6 Luna, Terra), seed 1

Plan B (DECISIONS D37). The buyer is the paid model with `reasoning_effort=low`, and the extractor is the frozen local gpt-oss:20b (D24). OBT default (b0 5%, W 0, δ 0), k = 1, 50 rounds, A2A. One seed, so no CIs. The gpt-oss rows are the same configs on seed 1 from E2c / E2, for reference. Terra has no `none` run: its utility cost is against Luna's `none` run, a cross-model reference.

## Loss from lies (mean of scenarios 2-12) = damage + reroute + resid

| run | attack runs | loss from lies | damage | reroute | resid |
|---|---|---|---|---|---|
| Luna obt+planner | 11 | 160.0 | 59.4 | 0.0 | 100.6 |
| Luna none | 11 | 908.9 | n/a | 0.0 | 908.9 |
| Terra obt+planner (utility vs Luna none) | 11 | 158.0 | 59.4 | 0.0 | 98.6 |
| gpt-oss obt+planner (E2c, s1) | 11 | 100.9 | 48.3 | 0.0 | 52.6 |
| gpt-oss none (E2, s1) | 11 | 2,127.5 | n/a | 0.0 | 2,127.5 |

## Damage vs bound (OBT runs; DESIGN §6)

| run | failure events | Σ damage | Σ bound | max damage/bound | bound held | invariant violations |
|---|---|---|---|---|---|---|
| Luna obt+planner | 73 | 653.5 | 1,748.0 | 0.526 | yes | 0 |
| Terra obt+planner (utility vs Luna none) | 73 | 653.5 | 1,748.0 | 0.526 | yes | 0 |
| gpt-oss obt+planner (E2c, s1) | 73 | 531.0 | 1,415.0 | 0.579 | yes | 0 |

## Utility (primary: cost − cost(none), same seed)

| run | utility cost, honest | % of none's honest cost | utility cost, noisy-honest | S_main unit share, honest |
|---|---|---|---|---|
| Luna obt+planner | 303.5 | 5.30% | 383.0 | 0.305 |
| Luna none | 0.0 | 0.00% | 0.0 | 0.927 |
| Terra obt+planner (utility vs Luna none) | 305.5 | 5.34% | 383.0 | 0.298 |
| gpt-oss obt+planner (E2c, s1) | 207.0 | 3.52% | 253.0 | 0.171 |
| gpt-oss none (E2, s1) | 0.0 | 0.00% | 0.0 | 0.570 |

## Extractor eval: the paid models' own extraction (frozen prompt)

| extractor | split | n | precision | recall | exact | honest→UNTESTABLE | injected recorded |
|---|---|---|---|---|---|---|---|
| llm:gpt-5.6-luna | test | 199 | 1.0 | 0.9898 | 0.9849 | 0.0 | 0 |
| llm:gpt-5.6-luna:test_hard | test_hard | 30 | 1.0 | 1.0 | 1.0 | None | 0 |
| rule | test | 199 | 1.0 | 1.0 | 1.0 | 0.0 | 0 |
| rule:test_hard | test_hard | 30 | 1.0 | 1.0 | 1.0 | None | 0 |
| llm:gpt-5.6-terra | test | 199 | 1.0 | 1.0 | 1.0 | 0.0 | 0 |
| llm:gpt-5.6-terra:test_hard | test_hard | 30 | 1.0 | 0.9333 | 0.9333 | None | 0 |

## Hard subset: shipping/ready/scheduled dates wrongly recorded as delivery deadlines (lower is better)

| extractor | LLM alone (no guard) | with the code guard |
|---|---|---|
| gpt-5.6-luna | 21/30 | 0/30 |
| gpt-5.6-terra | 18/30 | 0/30 |
| gpt-oss:20b (E4, reference) | 21/30 | 0/30 |

## Spend (runs/cost_ledger.jsonl; hard stop $16)

| model | part | calls | input tokens | output tokens | of which reasoning | $ |
|---|---|---|---|---|---|---|
| gpt-5.6-luna | eval runs (buyer) | 1,066 | 1,497,699 | 170,147 | 101,802 | 0.5037 |
| gpt-5.6-luna | extractor eval | 223 | 121,538 | 13,074 | 1,315 | 0.0400 |
| gpt-5.6-terra | eval runs (buyer) | 530 | 860,751 | 50,672 | 14,553 | 2.3296 |
| gpt-5.6-terra | extractor eval | 223 | 121,538 | 12,458 | 291 | 0.3926 |
| **total** | | 2,042 | | | | **3.2659** |
