# Memory fuzzy-match — product decision (Item 5)

**Status:** Decision ticket only — **no code** until a named choice after real usage evidence.

**Linear:** [STA-320](https://linear.app/staqbot/issue/STA-320/decision-memory-fuzzy-match-reopen-criteria-item-5)

## Current state

STA-316 Option B shipped: opaque-token / exact-match (HMAC on normalized mentions) for entity disambiguation. Fuzzy “which Sarah?” matching is **not** implemented.

## Reopen criteria

Reopen only if production usage shows repeated clarification pain for ambiguous person/entity mentions (e.g. multiple org members matching the same first name), documented with live chat traces — not from synthetic prompts alone.

## Options (named choice required)

| Option | Meaning | Governance |
|--------|---------|------------|
| **A — Keep exact-match** | Leave STA-316 as-is; clarify via chat when ambiguous | No new risk |
| **B — Non-PII heuristic** | Match on already-known org role/title/department context only — no raw email/name embeddings | Does **not** reopen third-party ML PII governance |
| **C — Embeddings / fuzzy** | Soft-match via embeddings | **Gated** on STA-312-style governance sign-off |

## Decision

**Deferred.** Default until evidence: **Option A**. Do not implement B or C without an explicit named choice in Linear after live usage evidence.
