# Progress
| Stage | Status | Summary |
|---|---|---|
| 1 Types + ledger | DONE | Frozen Claim/Action/Note models, illegal transitions raise, append-only Ledger/ActionLog/NoteLog with verifier capability key (25 tests). |
| 2 Environment + oracles | TODO | |
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
