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
| 8 LLM buyer agent | DONE | LLMBuyer (render-only context, code-derived values, block->replan, selfcheck veto, parse fallback). gpt-oss:20b honest OBT run $6,224.5 < backup-only $6,932.0 (seed 1, runs/stage8_gpt-oss-20b_obt_s1.json). |
| 9 TLA+ spec | DONE | TLC: I1-I4 hold on 80.7M states (small bounds); budget-check-removed mutant gives a 4-step I1 counterexample. |
| 10 Eval harness | DONE | eval/run.py (loss/utility/overhead/extractor tables, $13 hard stop, paid fail-closed), 200-message labeled set; scripted + fake-LLM end-to-end tests. |

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

### Stage 8 plan
- `obt/agent.py`: `LLMBuyer(llm, cfg, defense)` builds its prompt only from `render(view)`; JSON decision `{s_main_order: {cite, qty} | null, backup_qty, next_lot_request, note, note_cites}` validated by pydantic. OBT: order cites offer ids (qty/value derived by code); if the gate blocks, one follow-up call with the reason code to re-plan backup. `none`/`provenance`: orders by qty, no citations. `selfcheck`: extra LLM "is S_main trustworthy?" veto before each S_main order (logged as BLOCKED `SELF_CHECK`). Unparseable output -> no S_main order, base-stock backup fallback, counted in metrics.
- `obt/sim.py`: `BuyerAPI.veto` for the selfcheck baseline; buyer stats in metrics.
- `eval/stage8.py`: honest scenario, LLM buyer under OBT vs scripted backup-only on the same seed; writes `runs/stage8_*.json`.
- `tests/test_llm_buyer.py`: fake-backend tests (citations passed through, value never from the LLM, block -> re-plan call, bad JSON fallback, selfcheck veto, prompt has no raw text under OBT). Acceptance run on gpt-oss:20b (dev on gemma3:12b while it downloads).

### Stage 9 plan
- `spec/OBT.tla`: one counterparty; offer book -> ledger commit, gate with budget, verifier with nondeterministic outcomes + same-step flagging, notes, ticks. I1-I3 as action properties, I4 as a state invariant; `CHECK_BUDGET` switches the mutated gate.
- `spec/OBT.cfg` (3 claims, 3 actions, 1 note, values {1,2}, B0=1, W=1, 3 rounds) and `spec/OBT_mutant.cfg`; `spec/check.sh` runner (portable JDK in `tools/`, git-ignored).
- Result: correct gate 80,680,591 distinct states, no error (4m51s); mutant -> "Action property I1 is violated" after 4 states (order value 2 executes with B0 = 1).

### Stage 10 plan
- `eval/extractor_set/build.py` -> `messages.jsonl`: 200 seeded labeled messages (honest, relative time, delivery/price only, split, far, special, vague, distractor, negated, injection).
- `eval/run.py`: scenarios x defenses x seeds; per-run JSON lines, `summary.json` + `summary.md` with loss from lies, utility (scenarios 1, 9), overhead per round vs none, extractor P/R (rule + LLM). Paid path: `check_budget` before every run, `CostMeter` before every call, hard stop at $13 recorded in the report; never sets `OBT_ALLOW_PAID`. Baselines use `NullExtractor` so overhead is fair. Each eval logs its LLM calls to its own dir under `runs/`.
- `tests/test_eval.py`: scripted end-to-end, fake-LLM end-to-end with overhead, multiset scoring, hard stop at cap, paid refused without env flag.

## Fixes v2
| Item | Status | Summary |
|---|---|---|
| F0 Freeze old state | DONE | Stopped eval at 12/40, tagged `v1-pre-fixes`, moved runs to `runs/_invalid_v1/` (+README), branch `fixes-v2`. |
| F1 Fixed round order | DONE | `ROUND_ORDER` + `step()` in beer_game drive `Sim.phase_*`; gate decides after all proposals and commits at once; blocked ORDER qty rerouted to backup (replaces LLM replan); invoices posted next round; DESIGN §5 updated. Scenario-8 loss threshold xfail until F2. |
| F2 Gate claim-action binding | DONE | FIXES table gate (capacity, EDF consumption, exposure = consumed x claimed price, OVER_CLAIM/PRICE_MISMATCH/CLAIM_MISMATCH incl. lead time/OVERPAY), claims straight to ledger with LAPSED (D11), gated capped invoice payments (D14), H=8 cap (D15); D2 closed. Scripted: honest 0 FAILED, all lying scenarios OBT loss <= $197. |
| F3 Verifier allocation + grace | TODO | |
| F4 Remediation in code | TODO | |
| F5 Extractor hardening | TODO | |
| F6 Invariants: spec, monitors, mutants | TODO | |
| F7 Loss bound | TODO | |
| F8 Scenarios 11-12 | TODO | |
| F9 Reputation baseline | TODO | |
| F10 Message bank + extractor dataset | TODO | |
| F11 Real A2A transport | TODO | |
| F12 Reproducibility | TODO | |
| E1 Ablation grid | TODO | |
| E2 Main LLM eval gpt-oss:20b | TODO | |
| E3 Second family qwen3:8b | TODO | |
| E4 Extractor eval | TODO | |
| E5 Paid, prepare only | TODO | |
