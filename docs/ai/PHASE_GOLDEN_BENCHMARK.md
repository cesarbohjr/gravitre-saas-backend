# Golden benchmark CI (audit §34 item 8)

**Status:** STRUCTURAL in merge CI; live smoke isolated-org only  
**Date:** 2026-09-17  
**Anchor:** `Tell me what my website traffic was last month.`

## Merge gate (always)

`backend/tests/services/test_golden_benchmark_traffic.py` plus existing Phase A file:

| Scenario | Assertion |
|----------|-----------|
| A | Last calendar month bounds + GA4/GSC recipe + preflight compile, no clarify |
| B | Three properties; unique domain match auto-selects |
| C | Three unlabeled sites → one clarify with display names |
| D | AUTH_EXPIRED copy; no property ask |
| E | No analytics → connect guidance; no web-search detour |
| F | Model-guessed `property_id` overwritten by resolver |
| G | Dual-source plan; user copy uses Analytics/Search, not vendor names |

CI: `.github/workflows/ci.yml` step **Golden benchmark (Phase A + traffic scenarios)**. Also listed in `scripts/cognitive-regression-suite.mjs`.

## Live smoke (not merge-blocking)

`scripts/smoke-golden-benchmark-live.py` — isolated conversation org only.

- After Railway backend deploy
- Weekly + `workflow_dispatch` (`.github/workflows/golden-benchmark-live.yml`)
- Missing secrets or SHA mismatch → **NOT RUN** (exit 2)
- Connect-only isolated org typically yields scenario **E**

Evidence pointer is the artifact `docs/delivery/smoke-golden-benchmark-live.json` (`conversation_id` + `git_sha`). Do not treat a local pytest pass as production-fixed.
