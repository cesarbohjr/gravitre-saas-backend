# Text-response latency — Phase 1 mount blocking (closed)

**Status:** DONE on tip `8c21d5c1` (API `/health` matches local `HEAD`).  
**Checked:** 2026-08-06

## Root cause (confirmed, not assumed)

1. `collect_signals` ran predictive + early-warning + suggestions + org + failures **sequentially**.
2. `generate_early_warning_alerts` looped all domain packs and re-called `detect_suggestions_for_org` on each hit.
3. Advisor `generate_brief` called `collect_signals`, then department brief called **`collect_signals` again**.
4. Frontend `useSWR` fired `/api/assistant/business-signals` and `/api/assistant/advisor-brief` as soon as `user` hydrated, contending with conversation list / composer mount.

## Fixes shipped (commits)

| Commit | Change |
|--------|--------|
| `b38449f0` | Parallelize/cache signals; scope early-warning; reuse one collect for briefs; idle-defer SWR (`requestIdleCallback` / 2.5s) |
| `948689ef` | Mount endpoints `include_predictive=False` |
| `8c21d5c1` | Skip daily briefing on mount advisor path |

## Live API latency (authenticated JWT → `api.gravitre.app`)

Artifact: `docs/delivery/phase1-mount-latency-after.json` (before from tip `3d372c5d` baseline).

| Endpoint | Before (ms) | After p50 (ms) on `8c21d5c1` |
|----------|-------------|------------------------------|
| `/api/assistant/business-signals` | 5196 | **1541** |
| `/api/assistant/advisor-brief` | 4447 | **1606** |

After runs on tip: BS 2787 / 1541 / 1169; AB 1646 / 1606 / 1326.

## Live /ai time-to-interactive

Artifact: `docs/delivery/phase4-chat-tti-live.json` @ 2026-08-06T08:08:31Z

| Slice | ms |
|-------|-----|
| Script start → chat textarea interactive | 13898 (includes UI login + home shell) |
| `ai_navigation` → `chat_input_interactive` | **852** (13046 → 13898) |
| `mount_intel_before_interactive` | **[]** |

Defer proof (wait 4s after interactive): `docs/delivery/phase1-mount-defer-proof.json`

- `mount_intel_before_interactive`: **[]**
- `mount_intel_after_interactive`: `business-signals` @ +3662ms after interactive
- Verdict: **PASS** — side-rail intel is off the chat critical path

## Verdict

Phase 1 **DONE**. Mount blockers removed from critical path; source latency cut ~3×; live tip verified `8c21d5c1`. Remaining multi-second work on those endpoints is deferred post-TTI and no longer blocks typing.
