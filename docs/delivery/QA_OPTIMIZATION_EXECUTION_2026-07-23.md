# QA / optimization execution status (2026-07-23)

Tracks [full execution plan](.) Part 5 sequencing. Evidence labels per `docs/ENGINEERING_STANDARDS.md`.

## Part 1 — QA process

| Item | Status | Artifact |
|------|--------|----------|
| Test pyramid classification | **DONE (local)** | `docs/delivery/test-pyramid-audit-latest.json` via `scripts/audit-test-pyramid.py` |
| Flaky / harness-softening policy | **DONE** | `docs/ENGINEERING_STANDARDS.md` §6–7 |
| LLM quality suite manifest | **DONE** | `docs/delivery/llm-quality-test-suite.md` |
| Prompt injection battery | **NOT RUN** | Gap documented in manifest |
| Golden-signal dashboard | **PARTIAL** | `docs/delivery/golden-signals-ops-audit-2026-07-23.md` |
| CI: vitest in web job | **DONE (code)** | `.github/workflows/ci.yml` |
| CI: pnpm audit fails on high+ | **DONE (code)** | same (removed `continue-on-error`) |

## Part 2 — Frontend performance

| Item | Status | Notes |
|------|--------|-------|
| `@next/bundle-analyzer` | **DONE (code)** | `ANALYZE=true pnpm analyze` in `apps/web` |
| Marketing `"use client"` on `/` and `/pricing` | **AUDIT** | Both pages are client components — TTFB/SSR win requires server-shell refactor (not shipped) |
| Lodash wholesale imports | **PASS** | No `from 'lodash'` in `apps/web` source |
| Vercel Speed Insights 404 | **NOT CONFIRMED** | Only `@vercel/analytics` in layout; no Speed Insights package — re-check prod network tab if 404 persists |
| Lighthouse CI gate | **DONE (code)** | `.github/workflows/marketing-lighthouse.yml` + `apps/web/lighthouserc.json` — **NOT RUN** on CI until merged |
| Cold TTFB re-measure | **NOT RUN** | Run with `Cache-Control: no-cache` + multiple samples before claiming fix vs warm cache |

## Part 3 — Prompt / prefix caching

| Item | Status | Notes |
|------|--------|-------|
| Static-first message order | **Already correct** | system → history → dynamic user block |
| Stable tool schema order | **DONE (code)** | `_stable_tool_list()` in `unified_turn_reasoning_service.py` |
| Provider cache metrics | **DONE (code)** | `stream_options.include_usage` → `cached_prompt_tokens` in `latency_breakdown` |
| Live before/after TTFT | **NOT RUN** | Re-run `scripts/verify-unified-turn-task-ttft-live.py`; compare `cached_prompt_ratio` turn 2+ |
| Tool count 13→5 experiment | **NOT RUN** | Requires STA-305 battery at tighter cap |

## Part 4 — Cleanup / debt

| Item | Status |
|------|--------|
| Old pipeline removal | **NOT READY** | `docs/delivery/old-unified-pipeline-removal-audit-2026-07-23.md` |
| ESLint 313 warnings burn-down | **PENDING** |
| 230 connector no-test backlog | **PENDING** (P2 batches) |

## Next prod evidence (recommended order)

1. Merge CI + caching instrumentation → deploy backend → TTFT live script (report `cached_prompt_ratio`).
2. Merge Lighthouse workflow → tune thresholds if first CI run fails on real scores.
3. Bundle analyzer treemap → top-5 modules doc.
4. Prompt-injection battery design + first live run.
