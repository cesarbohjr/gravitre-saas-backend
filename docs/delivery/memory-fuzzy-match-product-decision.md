# Memory fuzzy-match — product decision (Item 5 / STA-320)

**Status:** Decision ticket only — **no code** until a named choice after real usage evidence.

**Linear:** [STA-320](https://linear.app/staqbot/issue/STA-320/decision-memory-fuzzy-match-reopen-criteria-item-5)

## Current state

STA-316 Option B shipped: opaque-token / exact-match (HMAC on normalized mentions) for entity disambiguation. Fuzzy “which Sarah?” matching is **not** implemented.

## Proposed reopen criteria (for review — not approved)

Reopen **only** when **all** of the following are true:

1. **Live volume:** ≥ **5** distinct production chats (different `conversation_id`s) in a rolling 30-day window where the user had to clarify an ambiguous person/entity mention after exact-match failed or asked “which X?”.
2. **Evidence pointers:** Each instance cited with `conversation_messages` id + timestamp (or chat run id), not synthetic prompts alone.
3. **False-positive risk acknowledged:** At least one example where exact-match correctly refused to guess (preserving safety) vs pain from over-clarifying.
4. **Named option chosen** in Linear after evidence review (A / B / C below) — a general “complete STA-320” is not authorization to implement B or C.

Until then: keep **Option A** (exact-match only).

## Soft signals (insufficient alone)

- Internal demo friction
- “It would be nicer if…” without live traces
- Single-org anecdotal request without the volume bar above

## Options (named choice required)

| Option | Meaning | Governance |
|--------|---------|------------|
| **A — Keep exact-match** | Leave STA-316 as-is; clarify via chat when ambiguous | No new risk — **default until evidence** |
| **B — Non-PII heuristic** | Match on already-known org role/title/department context only — no raw email/name embeddings | Does **not** reopen third-party ML PII governance; still needs explicit named choice |
| **C — Embeddings / fuzzy** | Soft-match via embeddings | **Gated** on STA-312-style governance sign-off (same territory as Memory Phase 1 pause) |

## Explicit non-goals until reopen

- No silent fuzzy resolve of person names
- No third-party ML on PII for “which Sarah?”
- No auto-pick of closest string match without user confirmation

## Decision

**Deferred.** Default until evidence: **Option A**. Do not implement B or C without an explicit named choice in Linear after live usage evidence meeting the reopen bar above.

## Review ask (Cesar)

Confirm or amend the volume bar (5 chats / 30 days) and whether Option B would ever be acceptable without Option C’s governance path.
