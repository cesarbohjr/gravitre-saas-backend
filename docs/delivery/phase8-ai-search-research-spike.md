# Phase 8 — AI Search research spike (API + scrape options)

**Status:** COMPLETE — **path locked 2026-07-15:** **C** (Ahrefs + Finseo dual BYO) + **S2** (UI scrape in v1) with scrape action tiers **v1 / v2 / v3**. Pack build in progress; tip smoke pending.  
**Date:** 2026-07-15 (updated: scrape path added; Cesar locked C + S2)  
**Program row:** Pack #8 — AI Search  
**Hard stop (unchanged):** LinkedIn scrape under any framing remains absolutely out of scope.  
**AI-answer scrape:** **Authorized** as path **S2** (consumer-UI capture in pack v1) with action tiers v1/v2/v3 — ToS / fragility / ops cost acknowledged.

---

## Verdict

| Question | Answer |
|----------|--------|
| Can we ship an AI Visibility pack without scraping? | **Yes** — licensed aggregator APIs (preferred) or first-party model APIs |
| Can we also cover consumer-UI answers via scrape? | **Yes, as an optional named path** — higher ToS/ops risk; not recommended as sole source |
| Best near-term path for Gravitree | **Ahrefs Brand Radar** on existing Marketing `ahrefs` BYO; add scrape only if Cesar wants consumer-UI parity |
| Build pack #8 now? | **Yes** — Cesar locked **C + S2** (scrape v1–v3); tip smoke after implement |
| Fit with Phase 1.5 / Pack KPI | Same as Marketing: `invoke_tool` → shared ingestion → PackSignal → PackKpiPanel |

---

## Problem statement (from Phase 0)

Vision source: *ChatGPT / Perplexity / Bing Copilot visibility*  
Agent: **AI Visibility Agent** (NEW)  
Repo state at spike start: **no** connector, catalog entry, or executor for LLM answer-engine visibility.

Goal of this spike: decide **how** we would measure brand presence inside AI answers — **API-first**, with **consumer-UI scrape** documented as an optional Cesar-gated path (not implemented in this spike).

---

## Surfaces: API vs scrape

| Surface | How | Pros | Cons |
|---------|-----|------|------|
| **Aggregator API** (Ahrefs Brand Radar, Finseo, …) | Licensed REST | Stable, `result_url`, pack-shaped | Plan entitlements; may lag consumer UI |
| **First-party model APIs** | OpenAI / Perplexity / Anthropic / Google keys | ToS-clean for that provider | Differs from logged-in app; multi-key ops |
| **Consumer-UI scrape** | Browser automation against chatgpt.com / perplexity.ai / bing.com/chat / gemini.google.com / copilot.microsoft.com | Closest to what buyers see | ToS risk, CAPTCHA/login drift, IP/proxy ops, brittle selectors, legal review |

**Signal quality note:** API answers often differ from consumer **app** answers (system prompts, browsing, personalization). If Cesar wants both, treat them as **two signals** (e.g. `visibility.api` vs `visibility.ui`), never merge blindly.

**Still forbidden without separate product decision:** LinkedIn scrape; cookie/session theft; attacking provider infra; persisting full scraped answer text into Memory/KG without Cesar sign-off.

---

## What default (API-only) allows vs scrape-gated

| Default allowed (no S choice) | Requires named scrape path **S1/S2** | Always forbidden |
|-------------------------------|--------------------------------------|------------------|
| Official vendor REST APIs | Playwright/Puppeteer (or equivalent) against named consumer UIs | LinkedIn scrape |
| First-party model APIs with search/citations | Managed runner (self-hosted or vetted vendor) for UI prompts | Credential stuffing / session hijack |
| Aggregators that call provider APIs under their ToS | Rate-limited prompt batches for mention/citation scoring | Scraping into Memory/KG without governance |
| CSV/manual GEO export upload | Storing scrape provenance (`source=ui_scrape`, URL, captured_at) | Undocumented “gray” Apify consumer-UI actors without Cesar review |

---

## Vendor shortlist (API-capable)

| Path | API? | Auth fit | Platforms claimed | Notes |
|------|------|----------|-------------------|-------|
| **Ahrefs Brand Radar** | **Yes** — `https://api.ahrefs.com/v3/brand-radar` | Reuse Marketing **`ahrefs` `byo_required`** | ChatGPT, Gemini, Perplexity, Copilot, Claude, Grok, Google AI Overviews / AI Mode | **Preferred API path** |
| **Finseo** | **Yes** — `https://api.finseo.ai/v1` | New **`byo_required`** | ChatGPT, Claude, Perplexity, Gemini, Google AI, Copilot | Strong alt |
| **Peec AI** | Yes (beta, Enterprise) | New BYO | ChatGPT, AI Mode/Overviews, Copilot, Perplexity, Gemini | Poor self-serve tip fit |
| **Profound** | Yes (enterprise) | New BYO | Broad | Sales-led |
| **First-party BYO keys** | Yes | Multi BYO | Per provider | High eng cost |
| **Semrush AI Toolkit** | No clear public GEO API in this spike | Existing `semrush` BYO | Dashboard-first | Do not assume coverage |
| **Apify / similar runners** | Mixed | Review per actor | Multi | Some claim official APIs (OK under API paths); **consumer-UI actors** only under **S1/S2** + Cesar review |

Sources: [Ahrefs Brand Radar API](https://docs.ahrefs.com/api/reference/brand-radar), [Finseo API](https://www.finseo.ai/developers/api), [Peec API intro](https://docs.peec.ai/api/introduction).

---

## Scrape path (research only — no PoC in this spike)

If Cesar picks **S1** or **S2**, build-later shape (high level):

1. **Isolated connector** `ai_visibility_ui` (or per-surface stubs) — never share cookies with user browsers.  
2. **Prompt library** = same ICP prompts as API path for A/B comparison.  
3. **Outputs:** mention boolean, rank-in-answer, cited domains, competitor co-mentions, screenshot/HTML hash optional.  
4. **Provenance:** `auth_mode` distinct from BYO API; every row tagged `capture_method=ui_scrape`.  
5. **Governance:** raw answer body → Memory/KG **STOP** by default (same as GSC raw query).  
6. **Ops:** expect selector breakage, login walls, geo variance; tip smoke must tolerate flaky UI and not block API tip.  
7. **Legal:** product/legal acknowledge provider ToS before smoke-org enablement.

This spike does **not** ship selectors, exploit PoCs, or live scrape jobs.

---

## Recommended architecture (when Cesar picks paths)

Mirror Marketing / RevOps — do **not** invent a parallel KG writer.

```
catalog: ai-search-intelligence-pack
  → install: ai_search_install.py (AI Visibility Agent + stub connectors)
  → auth_mode: byo_required (ahrefs and/or finseo)
  → optional: ai_visibility_ui (scrape) if S1/S2
  → actions: brand_radar.* / finseo.metrics.* / ui_visibility.check (gated)
  → pipeline: map_* → write_external_entity_with_provenance → PackSignal
  → UI: PackKpiPanel + result_url (vendor report and/or captured artifact URL)
  → tip smoke: docs/delivery/phase4-ai-search-pack-live.json (future)
```

**Boundary vs Marketing:** Marketing = classic SEO; AI Search = answer-engine visibility (API ± UI scrape). Reuse Ahrefs client; keep packs separate in marketplace.

**Memory/KG stop-line (proposed):**  
- Aggregates OK: mention rate, SoV, citation domains, prompt-level “mentioned”.  
- Raw full AI answer text (API or scrape) → Memory/KG **STOP** without Cesar sign-off.

---

## Build-path options — API (pick one)

| Option | What we build | Gate |
|--------|---------------|------|
| **A — Ahrefs Brand Radar first** *(recommended)* | Pack + Brand Radar on existing `ahrefs` BYO; stub Finseo | Brand Radar on customer Ahrefs plan |
| **B — Finseo BYO first** | New `finseo` connector + pack | Finseo API key on smoke org |
| **C — Dual BYO (Ahrefs + Finseo)** | Both; install uses whichever is connected | Two entitlements |
| **D — First-party model APIs only** | OpenAI/Perplexity/Anthropic/Gemini BYO + local scoring | Multi-key ops |
| **E — Hold pack build** | Spike only | Default until A–D chosen |

## Scrape options — add-on (pick one; combine with A–D)

| Option | Meaning |
|--------|---------|
| **S0 — No scrape** *(default / recommended with A)* | API (or hold) only; consumer UIs out of scope |
| **S1 — API primary + UI scrape gap-fill** | Ship A/B/C/D first; add limited UI scrape for prompts/surfaces APIs miss |
| **S2 — UI scrape included in v1** | Pack tip requires at least one consumer-UI capture path alongside or instead of aggregator (higher risk; not recommended as sole source) |

## Cesar path lock (2026-07-15)

| Dimension | Choice |
|-----------|--------|
| API | **C** — Ahrefs + Finseo dual BYO; install uses whichever is connected |
| Scrape | **S2** — UI scrape in pack v1 with action tiers **v1 / v2 / v3** |
| Finance (#9) | **F3** — QB + Xero + NetSuite (+ Plaid if entitled) |
| HR & Talent (#10) | **H3** — Workday + BambooHR + Greenhouse + Gusto |

Pack scaffold + connectors implemented on `main` (tip smoke still pending).

### Finance + HR lock append (2026-07-15)

Cesar locked **F3** and **H3** alongside AI Search **C + S2**. Scaffold on `main`:

| Pack | Path | Install / catalog | Notes |
|------|------|-------------------|-------|
| #8 AI Search | C + S2 | `ai-search-intelligence-pack` / `ai_search_install.py` | Brand Radar + Finseo BYO + `ai_visibility_ui` v1–v3 |
| #9 Finance | F3 | `finance-intelligence-pack` / `finance_install.py` | Plaid stubs call API if `access_token` present; else clear “exchange public_token” error. Vendor `shipped=False` until Link connect UX complete. |
| #10 HR | H3 | `hr-talent-intelligence-pack` / `hr_talent_install.py` | Gusto stubs fail closed asking for partner OAuth; UI partner gate unchanged (`shipped=False`). |

Stop-lines: raw AI answers / payroll-banking / employee+compensation PII → Memory/KG blocked; no LinkedIn scrape.

---

## Explicit non-goals (this spike — historical; scaffold now exists)

- ~~No Marketplace catalog entry / install~~ — scaffolded  
- Tip smoke / live prod evidence still pending  
- Deep Plaid Link exchange UI and Gusto partner OAuth client still gaps  
- Compliance / Business OS unchanged

---

## Finance / HR — **LOCKED** (Cesar 2026-07-15)

| Choice | Meaning |
|--------|---------|
| **F3** | All Finance live — QB + Xero + NetSuite + Plaid if entitled |
| **H3** | All HR live — Workday + BambooHR + Greenhouse + Gusto |

Historical options F0–F2 / H0–H2 retained below for audit only.

### Finance (#9) — options (historical)

| Choice | Meaning |
|--------|---------|
| **F0 — Hold** | No Finance intelligence pack; connectors stay dormant |
| **F1 — Scaffold only** | Catalog + mocked Cash Flow agent; **no** live QB/Xero/NetSuite/Plaid invokes |
| **F2 — Smoke QB only** | Live QuickBooks on smoke org only; Xero/NetSuite/Plaid stay gated |
| **F3 — All Finance live** | QB + Xero + NetSuite (+ Plaid if entitled) allowed for pack tip ← **SELECTED** |

### HR & Talent (#10) — options (historical)

| Choice | Meaning |
|--------|---------|
| **H0 — Hold** | No HR intelligence pack; connectors stay dormant |
| **H1 — Scaffold only** | Catalog + mocked Recruiting agent; **no** live HRIS/ATS/Payroll |
| **H2 — ATS only (Greenhouse)** | Live Greenhouse on smoke org; Workday/BambooHR/Gusto gated |
| **H3 — All HR live** | Workday + BambooHR + Greenhouse + Gusto allowed for pack tip ← **SELECTED** |

---

## Next steps after this artifact

1. Cesar picks API path **A / B / C / D / E** and scrape **S0 / S1 / S2**.  
2. Cesar picks Finance **F0–F3** and HR **H0–H3**.  
3. Only after those named choices: implement pack(s), tip smokes, update master program rows.

---

## Evidence / provenance

- Phase 0 vision: `docs/delivery/phase0-twelve-pack-marketplace-vision.md` (AI Visibility NEW; original gate “research spike — no scrape”)  
- This update: scrape added as **optional named path S0–S2** per Cesar request 2026-07-15  
- Program lock: `docs/delivery/master-knowledge-intelligence-packs-program.md` row 8  
- Marketing pattern: `marketing_install.py`, `auth_mode.py` (`ahrefs` BYO), Pack KPI Phase 3.5  
- Finance/HR: STA-312-class governance
