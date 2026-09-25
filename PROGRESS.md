# Progress
| Stage | Status | Summary |
|---|---|---|
| 1 Types + ledger | DONE | Frozen Claim/Action/Note models, illegal transitions raise, append-only Ledger/ActionLog/NoteLog with verifier capability key (25 tests). |
| 2 Environment + oracles | DONE | Seeded Beer Game (prepaid invoices, holding/backlog cost), read-only OracleView, honest main + backup suppliers, order-up-to buyer; reruns give identical cost. |
| 3 Verifier | TODO | |
| 4 Budget + gate | TODO | |
| 5 Dependency tracker | TODO | |
| 6 Scripted attackers | TODO | |
| 7 Extractor + memory view | TODO | |
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
