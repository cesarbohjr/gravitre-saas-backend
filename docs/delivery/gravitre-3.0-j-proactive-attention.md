# Gravitre 3.0-J — ranked safe READ notices (2026-09-21)

**Status:** Source **UNIT_TEST**. No auto high-risk WRITE. No invented SKUs / Enable / prices.

## What shipped

| Piece | Behavior |
|-------|----------|
| Ranking | impact, urgency, confidence, relevance, actionability, novelty |
| Cap | at most 3 notices; extras stay quiet |
| WRITE | high-risk write signals dropped; `write_allowed` always False |
| Investigation | `safe_read` only |

## Gate

- UNIT_TEST: `test_platform_execution_3_0_j_attention.py`
- Live proactive notices: **NOT RUN**

3.0-H/I remain **partially open**: live unique-entity bind **NOT RUN**; spoken HTTP traces **PASS** on `19b3e014`. Historical required CI `35622991537` on `6d563e3d` stays FAIL.
