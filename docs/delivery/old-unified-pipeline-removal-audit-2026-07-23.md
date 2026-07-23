# Old unified-turn pipeline removal audit (2026-07-23)

**Phase 4 sign-off:** combined battery PASS recorded in delivery docs.

**Removal status:** **NOT READY** — classical path still referenced in production code.

| Component | Still referenced by |
|-----------|---------------------|
| `conversational_turn_gate` | `agent_intelligence.py`, `unified_turn_reasoning_service` (turn shape), `unified_turn_pending_live`, classical fallback |
| `chat_action_mapper` | Classical NL execution, extensive pytest, registration contract |

**Action when ready:** Dedicated removal PR after grep proves zero live entrypoints for classical mapper/gate on unified-live orgs; re-run full Phase 4 + STA-305 batteries on prod.

**Do not delete in the same pass as QA/perf work** — maintenance burden is real but removal without reference audit risks live fallthrough.
