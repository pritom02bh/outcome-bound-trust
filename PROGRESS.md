# Progress
| Stage | Status | Summary |
|---|---|---|
| 1 Types + ledger | DONE | Frozen Claim/Action/Note models, illegal transitions raise, append-only Ledger/ActionLog/NoteLog with verifier capability key (25 tests). |
| 2 Environment + oracles | DONE | Seeded Beer Game (prepaid invoices, holding/backlog cost), read-only OracleView, honest main + backup suppliers, order-up-to buyer; reruns give identical cost. |
| 3 Verifier | DONE | DELIVERY/PRICE template registry, deadline-ordered step with sync listeners, receipt allocation against double counting (D9); pass/fail/boundary tests. |
| 4 Budget + gate | DONE | B(c) with cool-down (D3), P(c), §6 gate + offer staging (D4); hypothesis state machine checks I1 and I2, and catches gate mutants. |
| 5 Dependency tracker | DONE | Verifier listener flags citing actions + notes inside the failing step, replan hooks, late notes flagged on entry; I4 hypothesis machine (found + fixed duplicate-citation bug). |
| 6 Scripted attackers | DONE | Gateway, rule extractor, offer book, sim loop + BuyerAPI, pulse-scripted buyer (D10), scenarios 1-10; deterministic traces for obt/none, per-scenario checks, OBT loss < no-defense loss. |
| 7 Extractor + memory view | DONE | LLM backend (logged, cached, paid calls fail closed, $13 CostMeter), pydantic-validated LLMExtractor (bad output -> UNTESTABLE), render(); I5 canary/injection, slot-smuggling, structural tests; live test passes on gemma3:12b. |
| 8 LLM buyer agent | TODO | |
| 9 TLA+ spec | TODO | |
| 10 Eval harness | TODO | |

## Notes

### Stage 1 plan
- `obt/types.py`: slot models (closed types), `Claim`, `Action`, `Note`, `Message` as frozen pydantic models; transitions via `with_status` that raise `IllegalTransition`.
- `obt/ledger.py`: `Ledger` (append-only claims, event log, verifier capability key, exposure only on PENDING), `ActionLog`, `NoteLog`.
- `tests/test_types_ledger.py`: every illegal transition raises, frozen fields, no delete/overwrite API, duplicate append raises, resolve needs verifier key, event log only grows.

### Stage 2 plan
- `obt/env/oracles.py`: `Receipt`, `Invoice` records; `Oracles` (writer, env-only) and `OracleView` (read-only queries: received qty in (lo, hi], invoices in [lo, hi)).
- `obt/env/beer_game.py`: `GameConfig`, seeded demand series, `Supplier` base, `BackupSupplier` (+20% price, lead 3), `HonestSupplier` (S_main, lead 2, offers lots); `BeerGame` with `begin_round` (arrivals -> receipts, demand, holding/backlog cost), `place_order` (invoice -> purchase cost, shipments), `pay`, buyer-belief pipeline, `cost_breakdown`.
- `obt/agent.py`: `OrderUpToBuyer` scripted policy; `run_plain` loop (no defense) for env-only tests.
- `tests/test_env.py`: rerun determinism (identical cost), different seeds differ, cost accounting by hand on a tiny config, oracle view is read-only, backup-only vs honest-main costs.

### Stage 3 plan
- `obt/verifier.py`: pure template checks `check_delivery`, `check_price` in a fixed registry; `Verifier(ledger, oracles, allocate_receipts=True)` binds the ledger key, `step(now)` resolves PENDING claims with deadline <= now in deadline order and notifies listeners synchronously (for stage 5).
- `tests/test_verifier.py`: pass/fail for both templates; boundary rounds (receipt at created_round excluded, at by_round included, at by_round+1 too late; invoice at created_round included, at valid_until excluded; price equal passes, one cent above fails; vacuous PRICE); not resolved before deadline; UNTESTABLE ignored; no double counting (D9) and literal mode shows the gap.

### Stage 4 plan
- `obt/ledger.py`: add `OfferBook` (staged claims not yet relied on, D4).
- `obt/budget.py`: `BudgetConfig(b0, window, backup)`, `TrustBudget.B(c, now)` with cool-down rule (D3), `pending(c)` = value of executed actions citing >=1 PENDING claim of c.
- `obt/gate.py`: `Gate.allow` = DESIGN §6 pseudocode (+ `UNKNOWN_CLAIM` for ids in neither store); `Gate.submit` logs PROPOSED, gates, commits staged claims, executes, adds exposure to cited PENDING claims (D1).
- `tests/test_budget_gate.py`: unit tests per reason code and budget formula; hypothesis `RuleBasedStateMachine` over random claims, oracle events, verifier ticks and actions checking I1 after every execution and I2 (B rises only in a verifier step that PASSED a claim of c).

### Stage 5 plan
- `obt/deps.py`: `DependencyTracker(ledger, actions, notes, verifier)` subscribes to verifier resolutions; on FAILED flags every EXECUTED/PROPOSED action and every note citing the claim inside the verifier step, then fires replan hooks with a `FailureEvent`. `add_note` flags at once if a cited claim is already FAILED.
- `tests/test_deps.py`: flags in the same step (flagged_round == failing round, before `step` returns), passing claims flag nothing, blocked actions untouched, hook fires once per failure, late note citing a FAILED claim is flagged; hypothesis state machine asserting I4 after every step.

### Stage 6 plan
- `obt/extractor.py`: `Extractor` base (`extract(msg) -> list[Claim]`, invalid spec -> UNTESTABLE, nothing -> one UNTESTABLE) and deterministic `RuleExtractor` (regex over supplier phrasings). LLM extractor comes in stage 7.
- `obt/gateway.py`: authenticated receive, append-only raw audit log, extraction into the offer book.
- `obt/memory_view.py`: structured `MemoryView` (state, offer cards, track record, B/P/headroom, notes, blocks, failures). Rendering + I5 test in stage 7.
- `obt/sim.py`: round loop (arrivals/demand -> verifier+deps -> offer -> buyer acts through a `BuyerAPI` that gates each order -> notes/request), defenses `obt` and `none`, per-round trace, loss-from-lies helper.
- `obt/agent.py`: `ScriptedClaimBuyer` (base-stock need, accepts main offer if price <= backup and lot <= need + slack, headroom-aware request under OBT, backup covers the rest).
- `obt/attacks/suppliers.py`: scenarios 1-10 from DESIGN §9 + `make_supplier(n, cfg, seed)`.
- `tests/test_scenarios.py`: every scenario x {obt, none} produces an identical trace on rerun; per-scenario behaviour checks (which claims fail, UNTESTABLE blocks, far deadlines stay pending, I1 holds every round under OBT, OBT loss <= none loss for lying scenarios).

### Stage 7 plan
- `obt/llm.py`: `LLM(backend, model)` for `ollama` | `openai` | `fake`; JSON-schema output; every call logged to `runs/llm_calls.jsonl` (model, tokens, latency, purpose); optional disk cache; `openai` refuses unless `OBT_ALLOW_PAID=1`; `CostMeter` with persistent hard cap (fails closed on unknown prices).
- `obt/extractor.py`: `LLMExtractor` with a flat JSON schema validated by pydantic; bad JSON/schema -> UNTESTABLE; bad slot values -> that claim UNTESTABLE.
- `obt/memory_view.py`: `render(view)` -> agent prompt text from structured fields only; raw messages only for the `none`/`selfcheck` baselines.
- `tests/test_extractor_view.py`: fake-backend schema tests; I5: structural (memory_view/agent never import gateway/Message), canary run (injection supplier with unique canaries; spy buyer records every rendered context; no canary/raw substring under OBT, present under `none` as positive control), slot smuggling blocked; live ollama smoke test marked `llm`.
