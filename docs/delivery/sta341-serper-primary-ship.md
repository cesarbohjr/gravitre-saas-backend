# STA-341 — Serper primary + Tavily fallback (ship)

**Date:** 2026-08-11  
**Pricing model:** unchanged (customer allotments 10/60/200, overage $0.35)  
**Serper free 2,500:** platform test/COGS only — not customer allotments

## Phase 0 — widened sample (GO)

| Metric | Result |
| -- | -- |
| N | **18** fresh representative queries |
| Hold rate | **1.0** (18/18) |
| Serper worse/empty/error | **0** |
| Avg latency | Serper **1068ms** / Tavily **2246ms** |
| Verdict | **GO** — proceed to Phase 1 |

Artifact: `docs/delivery/sta341-phase0-widen-sample.json` (+ `.md`)

Two queries flagged `no_domain_overlap` (React vs Vue; next federal holiday) but both providers still returned usable results with numeric/token agreement — not Serper failures.

## Phase 1 — integration

- `_search_serper` in `web_research.py` (POST `https://google.serper.dev/search`)
- `WEB_RESEARCH_PROVIDER=serper` primary; hard failure → Tavily with **visible** `web_research_fallback_to_tavily` / `web_research_fallback_served` logs
- `usage_records.metadata.provider` = actual server (`serper` or `tavily`); `fallback_from` when fallback
- `SERPER_API_KEY` via Railway secrets (not hardcoded)

## Phase 2 — verification checklist

- [ ] Live lookup meters `provider=serper`
- [ ] Forced invalid Serper key → Tavily fallback + `fallback_from=serper`
- [ ] Billing plans still 10/60/200 @ $0.35
- [ ] Golden signals `research_lookups` Serper % / fallback % wired
- [ ] Deployed `/health` `git_sha` matches tip
