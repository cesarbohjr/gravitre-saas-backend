# Conversational phrase variety (Module D expression range — pass 2)

Expands **how many ways** Gravitree can say the same conversational category.
Does **not** change `conversational_turn_gate`, pending-reply classifier, or write-authority.

SoT: [`voice_expression_range.py`](../../backend/app/services/voice_expression_range.py) +
[`conversational_reply_service.py`](../../backend/app/services/conversational_reply_service.py).

## Phase 1 — Inventory

| # | Category | Call sites | Was identical? | This pass |
|---|----------|------------|----------------|-----------|
| 1 | `conversational.greeting` | `generate_conversational_reply` / `_fallback` | **yes** (one house line) | **varied** (7) |
| 2 | `conversational.small_talk` | same | **yes** (shared house line) | **varied** (7) |
| 3 | `conversational.thanks` | same + mixed ack | **yes** | **varied** (7) + mixed ack bank |
| 4 | `conversational.banter` | same + mixed ack | **yes** | **varied** (7) + mixed ack bank |
| 5 | `conversational.venting` | same | **yes** | **varied** (7) |
| 6 | `tool_error.connector_not_connected` / `connector_connect_to_run` | envelope + adapter | already varied | **confirmed** |
| 7 | `missing_parameters_header` | operator response | already varied | **confirmed** |
| 8 | write approval (`write_approval*`, `approval_needed_requester`) | workflows / connector | shaped / fixed | **excluded** |
| 9 | `success_win` / `success_win_light` | Meson + digest | already varied | **confirmed** |
| 10 | `tool_error.*` failure banks | adapter | already varied | **confirmed** (+ fact sample) |
| 11 | `conversational.meta_capability` | meta conversational path | mostly one template | **varied** (6, `{capability}` fact slot) |
| 12 | task completed + recommendation | Meson success + guidance | success banks vary; recs data-driven | no new bank |
| 13 | Other recurring: `insufficient_info`, `assumption_flag`, `correction_ack`, `blocked_generic`, `pending_plan_cancelled`, `skipped_*`, `estimate_prefix` | gravitree_voice | already varied in pass 1 | **confirmed** |

### Excluded (precision / governance)

- `write_approval`, `write_approval_required`, `canvas_write_blocked`, `approval_needed_requester(+title)`
- Notification / audit / failure alert titles

Why: CTA and Decision Queue wording must stay audit-stable.

## Phase 3 — Selection

- Same as pass 1: `task_state.voice_expression_last` → `{category: last_index}`
- Bound in `execute_task_streaming` via `bind_voice_expression_state`
- Rule: `next = 0` if unset; else `(last + 1) % n` — no RNG
- Conversational path is **bank-first** for priority categories (no model paraphrase that collapses to one house line)

## Verification

```bash
pytest backend/tests/services/test_voice_expression_range.py \
  backend/tests/services/test_conversational_turn_gate.py -q
EXPECT_SHA=<tip> python scripts/verify-conversational-phrase-variety-live.py
# Regression samples:
EXPECT_SHA=<tip> python scripts/verify-conversational-path-live.py
# (pending-reply 24-case when credentials allow)
```

Artifact: [`conversational-phrase-variety-live.json`](conversational-phrase-variety-live.json)
