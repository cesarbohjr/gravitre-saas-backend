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
- Live proactive notices: **PASS** — 2 ranked `safe_read` notices from live GA/GSC `misconfigured` readiness; `write_allowed=false`; cap 3. Artifact `gravitre-3.0-closeout-live.json` @ `7a2eaaab`.

3.0-H unique Alpha bind **PASS** (synthetic bindings). Spoken HTTP traces **PASS**. Historical required CI `35622991537` on `6d563e3d` stays FAIL.
