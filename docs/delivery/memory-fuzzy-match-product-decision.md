# Memory fuzzy-match — product decision (Item 5 / STA-320)

**Status:** **Option B chosen and implemented** (2026-07-18).

**Linear:** [STA-320](https://linear.app/staqbot/issue/STA-320/decision-memory-fuzzy-match-reopen-criteria-item-5)

## Current state

- STA-316 opaque-token / exact HMAC Memory path remains opt-in (unchanged).
- **STA-320 Option B shipped:** non-PII role/title cue heuristic against `org_entity_resolution_records` with `entity_type=role`.
- Exact alias + role heuristic run **without** Memory opt-in. Opaque Memory search still requires opt-in.
- Option C (embeddings/fuzzy person names) is **not** authorized.

## Proposed reopen criteria (historical — amended)

Originally: reopen B/C only when ≥5 distinct prod “which X?” chats / 30 days + named choice.

**Amendment (2026-07-18):** Cesar named **Option B** explicitly; the volume bar was **waived** for B only so implementation could proceed. Option C remains gated on governance + evidence.

## Soft signals (insufficient alone for Option C)

- Internal demo friction
- “It would be nicer if…” without live traces
- Single-org anecdotal request without a volume bar / governance sign-off

## Options

| Option | Meaning | Status |
|--------|---------|--------|
| **A — Keep exact-match** | Leave STA-316 as-is | Superseded for role cues by B |
| **B — Non-PII heuristic** | Match already-known org role/title/department aliases only | **Chosen + shipped** |
| **C — Embeddings / fuzzy** | Soft-match via embeddings | **Not authorized** — gated |

## Explicit non-goals (still in force)

- No silent fuzzy resolve of person names
- No third-party ML on PII for “which Sarah?”
- No auto-pick of closest string match without user confirmation
- No lowering Memory `min_score` / softening HMAC (Option C territory)

## Decision

**Option B** (2026-07-18). Volume bar waived for this named choice only.

### Implementation map

- `backend/app/services/memory_role_title_heuristic.py` — cue extract, match, learn
- `backend/app/services/memory_field_resolver.py` — order: exact → role → Memory (opt-in)
- `backend/app/services/connector_action_workflows.py` — learn role aliases on unique bind
- Tests: `backend/tests/services/test_memory_role_title_heuristic.py`

Ship SHA: `09e57595` (PR [#164](https://github.com/cesarbohjr/gravitre-saas-backend/pull/164); prod health confirmed 2026-07-18).
