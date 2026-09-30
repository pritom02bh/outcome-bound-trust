# E5: paid buyers (GPT-5.6 Luna, Terra), seed 1

DECISIONS D37, D37a. The buyer is the paid model with `reasoning_effort=low`, and the extractor is the frozen local gpt-oss:20b (D24). OBT default (b0 5%, W 0, δ 0), k = 1, 50 rounds, A2A. One seed, so no CIs.

- **v2** (current): every buyer call sampled fresh; the reply cache is scoped to one run and call index (resume only). Terra has its own `none` baseline.
- **v1** (superseded: cross-run reply reuse): byte-identical prompts in another run reused an earlier paid reply (134/1,200 Luna and 70/600 Terra buyer calls). Terra's utility there was against Luna's `none`.
- **ref**: the same configs with the local gpt-oss buyer on seed 1 (E2c / E2).

## Loss from lies (mean of scenarios 2-12) = damage + reroute + resid

| version | run | attack runs | loss from lies | damage | reroute | resid |
|---|---|---|---|---|---|---|
| v2 | Luna obt+planner | 11 | 160.0 | 59.4 | 0.0 | 100.6 |
| v1 | Luna obt+planner | 11 | 160.0 | 59.4 | 0.0 | 100.6 |
| v2 | Luna none | 11 | 812.8 | n/a | 0.0 | 812.8 |
| v1 | Luna none | 11 | 908.9 | n/a | 0.0 | 908.9 |
| v2 | Terra obt+planner | 11 | 158.0 | 59.4 | 0.0 | 98.6 |
| v1 | Terra obt+planner (vs Luna none) | 11 | 158.0 | 59.4 | 0.0 | 98.6 |
| v2 | Terra none | 11 | 942.2 | n/a | 0.0 | 942.2 |
| ref | gpt-oss obt+planner (E2c, s1) | 11 | 100.9 | 48.3 | 0.0 | 52.6 |
| ref | gpt-oss none (E2, s1) | 11 | 2,127.5 | n/a | 0.0 | 2,127.5 |

## Damage vs bound (OBT runs; DESIGN §6)

| version | run | failure events | Σ damage | Σ bound | max damage/bound | bound held | invariant violations |
|---|---|---|---|---|---|---|---|
| v2 | Luna obt+planner | 73 | 653.5 | 1,748.0 | 0.526 | yes | 0 |
| v1 | Luna obt+planner | 73 | 653.5 | 1,748.0 | 0.526 | yes | 0 |
| v2 | Terra obt+planner | 73 | 653.5 | 1,748.0 | 0.526 | yes | 0 |
| v1 | Terra obt+planner (vs Luna none) | 73 | 653.5 | 1,748.0 | 0.526 | yes | 0 |
| ref | gpt-oss obt+planner (E2c, s1) | 73 | 531.0 | 1,415.0 | 0.579 | yes | 0 |

## Utility (primary: cost − cost(none), same seed, same buyer model unless noted)

| version | run | utility cost, honest | % of none's honest cost | utility cost, noisy-honest | S_main unit share, honest |
|---|---|---|---|---|---|
| v2 | Luna obt+planner | 322.0 | 5.65% | 404.5 | 0.304 |
| v1 | Luna obt+planner | 303.5 | 5.30% | 383.0 | 0.305 |
| v2 | Luna none | 0.0 | 0.00% | 0.0 | 0.952 |
| v1 | Luna none | 0.0 | 0.00% | 0.0 | 0.927 |
| v2 | Terra obt+planner | 312.0 | 5.46% | 409.5 | 0.298 |
| v1 | Terra obt+planner (vs Luna none) | 305.5 | 5.34% | 383.0 | 0.298 |
| v2 | Terra none | 0.0 | 0.00% | 0.0 | 0.940 |
| ref | gpt-oss obt+planner (E2c, s1) | 207.0 | 3.52% | 253.0 | 0.171 |
| ref | gpt-oss none (E2, s1) | 0.0 | 0.00% | 0.0 | 0.570 |

## Extractor eval: the paid models' own extraction (frozen prompt; per item, from v1, not re-paid)

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

## Spend (runs/cost_ledger.jsonl; hard stop $16 over v1 + v2)

| version | model | part | calls | input tokens | output tokens | of which reasoning | $ |
|---|---|---|---|---|---|---|---|
| v1 | gpt-5.6-luna | eval runs (buyer) | 1,066 | 1,497,699 | 170,147 | 101,802 | 0.5037 |
| v1 | gpt-5.6-luna | extractor eval | 223 | 121,538 | 13,074 | 1,315 | 0.0400 |
| v1 | gpt-5.6-terra | eval runs (buyer) | 530 | 860,751 | 50,672 | 14,553 | 2.3296 |
| v1 | gpt-5.6-terra | extractor eval | 223 | 121,538 | 12,458 | 291 | 0.3926 |
| v2 | gpt-5.6-luna | eval runs (buyer) | 1,200 | 1,675,450 | 185,765 | 108,030 | 0.5580 |
| v2 | gpt-5.6-terra | eval runs (buyer) | 1,200 | 1,730,207 | 158,282 | 73,313 | 5.3598 |
| **v1 total** | | | | | | | **3.2659** |
| **v2 total** | | | | | | | **5.9178** |
| **total (ledger)** | | | 4,442 | | | | **9.1837** |
