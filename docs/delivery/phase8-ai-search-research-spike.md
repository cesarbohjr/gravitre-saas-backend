# Phase 8 — AI Search research spike (API + scrape options)

**Status:** **DONE** — research closed 2026-07-17.  
**Path lock (Cesar 2026-07-15):** **C** (Ahrefs + Finseo dual BYO) + **S2** (UI scrape in v1) with action tiers **v1 / v2 / v3**.  
**Program row:** Pack #8 — AI Search  
**Hard stop (unchanged):** LinkedIn scrape under any framing remains absolutely out of scope.  
**AI-answer scrape:** **Authorized** as path **S2** — ToS / fragility / ops cost acknowledged; tip smoke is **out of this spike**.

---

## Closure (2026-07-17)

| Deliverable | Result |
|-------------|--------|
| API vs scrape decision matrix | Locked — dual BYO + UI scrape |
| Vendor shortlist | Ahrefs Brand Radar preferred; Finseo dual; Peec/Profound deferred |
| Scrape path shape (S2) | Named surfaces, provenance, Memory/KG stop-line |
| Action tiers v1/v2/v3 | Specified below (research contract for pack build) |
| Architecture fit | Same Marketing pattern: `invoke_tool` → PackSignal → PackKpiPanel |
| Live tip smoke | **Not in spike** — tracked as pack build follow-on |

**Research questions answered.** Remaining Pack #8 work is implementation evidence (`phase4-ai-search-pack-live.json` tip), not further vendor research.

---

## Verdict

| Question | Answer |
|----------|--------|
| Can we ship an AI Visibility pack without scraping? | **Yes** — licensed aggregator APIs (preferred) or first-party model APIs |
| Can we also cover consumer-UI answers via scrape? | **Yes, path S2** — higher ToS/ops risk; not sole source |
| Best near-term path for Gravitre | **C + S2** — Ahrefs Brand Radar + Finseo BYO; UI scrape alongside |
| Build pack #8 now? | **Scaffold exists on `main`**; tip smoke is the next build gate |
| Fit with Phase 1.5 / Pack KPI | Same as Marketing: `invoke_tool` → shared ingestion → PackSignal → PackKpiPanel |

---

## Problem statement (from Phase 0)

Vision source: *ChatGPT / Perplexity / Bing Copilot visibility*  
Agent: **AI Visibility Agent** (NEW)  
Repo state at spike start: **no** connector, catalog entry, or executor for LLM answer-engine visibility.

Goal of this spike: decide **how** we measure brand presence inside AI answers — **API-first**, with **consumer-UI scrape** as a Cesar-gated path.

---

## Surfaces: API vs scrape

| Surface | How | Pros | Cons |
|---------|-----|------|------|
| **Aggregator API** (Ahrefs Brand Radar, Finseo, …) | Licensed REST | Stable, `result_url`, pack-shaped | Plan entitlements; may lag consumer UI |
| **First-party model APIs** | OpenAI / Perplexity / Anthropic / Google keys | ToS-clean for that provider | Differs from logged-in app; multi-key ops |
| **Consumer-UI scrape** | Browser automation against allowlisted UIs | Closest to what buyers see | ToS risk, CAPTCHA/login drift, brittle selectors |

**Signal quality note:** API answers often differ from consumer **app** answers. Treat as **two signals** (`visibility.api` vs `visibility.ui`); never merge blindly.

**Still forbidden:** LinkedIn scrape; cookie/session theft; attacking provider infra; persisting full scraped answer text into Memory/KG without Cesar sign-off.

---

## What default (API-only) allows vs scrape-gated

| Default allowed (no S choice) | Requires named scrape path **S1/S2** | Always forbidden |
|-------------------------------|--------------------------------------|------------------|
| Official vendor REST APIs | Playwright/Puppeteer (or equivalent) against named consumer UIs | LinkedIn scrape |
| First-party model APIs with search/citations | Managed runner for UI prompts | Credential stuffing / session hijack |
| Aggregators that call provider APIs under their ToS | Rate-limited prompt batches for mention/citation scoring | Scraping into Memory/KG without governance |
| CSV/manual GEO export upload | Storing scrape provenance (`source=ui_scrape`, URL, captured_at) | Undocumented “gray” Apify consumer-UI actors without Cesar review |

---

## Vendor shortlist (API-capable)

| Path | API? | Auth fit | Platforms claimed | Notes |
|------|------|----------|-------------------|-------|
| **Ahrefs Brand Radar** | **Yes** — `https://api.ahrefs.com/v3/brand-radar` | Reuse Marketing **`ahrefs` `byo_required`** | ChatGPT, Gemini, Perplexity, Copilot, Claude, Grok, Google AI Overviews / AI Mode | **Preferred API path** |
| **Finseo** | **Yes** — `https://api.finseo.ai/v1` | New **`byo_required`** | ChatGPT, Claude, Perplexity, Gemini, Google AI, Copilot | Strong dual |
| **Peec AI** | Yes (beta, Enterprise) | New BYO | ChatGPT, AI Mode/Overviews, Copilot, Perplexity, Gemini | Poor self-serve tip fit |
| **Profound** | Yes (enterprise) | New BYO | Broad | Sales-led |
| **First-party BYO keys** | Yes | Multi BYO | Per provider | High eng cost — path **D** deferred |
| **Semrush AI Toolkit** | No clear public GEO API in this spike | Existing `semrush` BYO | Dashboard-first | Do not assume coverage |
| **Apify / similar runners** | Mixed | Review per actor | Multi | Consumer-UI actors only under **S1/S2** + Cesar review |

Sources (re-checked 2026-07-17): [Ahrefs Brand Radar API](https://docs.ahrefs.com/api/reference/brand-radar), [Finseo API](https://www.finseo.ai/developers/api), [Peec API intro](https://docs.peec.ai/api/introduction).

### API surface map (research contract)

**Ahrefs Brand Radar** (`/v3/brand-radar`) — overview family used for pack v1 tip:

| Family | Example endpoints | Pack signal |
|--------|-------------------|-------------|
| Overview | impressions / citations / mentions / SoV overview | Mention rate, SoV, citation domains |
| History | `*-history` variants | Trend series for PackKpiPanel |
| Prompts / competitors / exports | prompts list/track, competitors compare, exports | v2–v3 write/export actions |

**Finseo** (`/v1`) — dual BYO when Ahrefs Brand Radar unavailable:

| Group | Example | Pack signal |
|-------|---------|-------------|
| Projects | `GET /v1/projects` | Tenant brand context |
| Metrics | project metrics + timeseries | visibilityRate, mentions |
| Prompts / competitors / sources | list + ranking | Prompt coverage, SoV, citations |
| Export | bulk export | Warehouse / CSV tip path |

Install rule for **C:** use whichever of `ahrefs` / `finseo` is connected; UI scrape is additive, not a substitute for both APIs being down.

---

## Scrape path S2 — research shape

1. **Isolated connector** `ai_visibility_ui` — never share cookies with user browsers.  
2. **Allowlisted surfaces only:** ChatGPT, Perplexity, Gemini, Copilot, Claude (entry URLs in connector).  
3. **Prompt library** = same ICP prompts as API path for A/B comparison.  
4. **Outputs:** mention boolean, rank-in-answer, cited domains, competitor co-mentions; optional screenshot/HTML hash.  
5. **Provenance:** every row tagged `capture_method=ui_scrape`; distinct `auth_mode` from BYO API.  
6. **Governance:** raw answer body → Memory/KG **STOP** by default.  
7. **Ops:** tip smoke must tolerate flaky UI and **not** block API tip PASS.  
8. **Legal:** product/legal acknowledge provider ToS before smoke-org enablement of live UI capture.

This spike does **not** ship exploit PoCs or require live scrape tip PASS to close research.

### Scrape action tiers (S2 contract)

| Tier | Intent | Actions (research → catalog) | Gate |
|------|--------|------------------------------|------|
| **v1** | Read / single check | `ai_visibility_ui.surfaces.list`, `ai_visibility_ui.mentions.check` | Allowlisted surface + brand + prompt; provenance required |
| **v2** | Batch / write-shaped | `ai_visibility_ui.prompts.batch` | Rate limit; max checks per call; approval-friendly |
| **v3** | Advanced export | `ai_visibility_ui.captures.export` | Provenance bundle only; no Memory/KG raw body |

---

## Recommended architecture (locked)

Mirror Marketing / RevOps — do **not** invent a parallel KG writer.

```
catalog: ai-search-intelligence-pack
  → install: ai_search_install.py (AI Visibility Agent + stub connectors)
  → auth_mode: byo_required (ahrefs and/or finseo)
  → optional: ai_visibility_ui (scrape) under S2
  → actions: brand_radar.* / finseo.metrics.* / ui_visibility.* (v1–v3)
  → pipeline: map_* → write_external_entity_with_provenance → PackSignal
  → UI: PackKpiPanel + result_url (vendor report and/or capture artifact)
  → tip smoke: docs/delivery/phase4-ai-search-pack-live.json (build follow-on)
```

**Boundary vs Marketing:** Marketing = classic SEO; AI Search = answer-engine visibility (API ± UI scrape). Reuse Ahrefs client; keep packs separate in marketplace.

**Memory/KG stop-line:**  
- Aggregates OK: mention rate, SoV, citation domains, prompt-level “mentioned”.  
- Raw full AI answer text (API or scrape) → Memory/KG **STOP** without Cesar sign-off.

---

## Build-path options — API (historical; C selected)

| Option | What we build | Gate |
|--------|---------------|------|
| **A — Ahrefs Brand Radar first** | Pack + Brand Radar on existing `ahrefs` BYO; stub Finseo | Brand Radar on customer Ahrefs plan |
| **B — Finseo BYO first** | New `finseo` connector + pack | Finseo API key on smoke org |
| **C — Dual BYO (Ahrefs + Finseo)** ← **LOCKED** | Both; install uses whichever is connected | Two entitlements |
| **D — First-party model APIs only** | OpenAI/Perplexity/Anthropic/Gemini BYO + local scoring | Multi-key ops — deferred |
| **E — Hold pack build** | Spike only | Superseded by C + S2 |

## Scrape options (historical; S2 selected)

| Option | Meaning |
|--------|---------|
| **S0 — No scrape** | API (or hold) only |
| **S1 — API primary + UI scrape gap-fill** | Ship API first; limited UI later |
| **S2 — UI scrape included in v1** ← **LOCKED** | Pack includes consumer-UI capture path + tiers v1–v3 |

## Cesar path lock (2026-07-15)

| Dimension | Choice |
|-----------|--------|
| API | **C** — Ahrefs + Finseo dual BYO; install uses whichever is connected |
| Scrape | **S2** — UI scrape in pack v1 with action tiers **v1 / v2 / v3** |
| Finance (#9) | **F3** — QB + Xero + NetSuite (+ Plaid if entitled) — **live connect still HOLD** |
| HR & Talent (#10) | **H3** — Workday + BambooHR + Greenhouse + Gusto — **live connect still HOLD** |

### Finance + HR lock append (2026-07-15)

| Pack | Path | Install / catalog | Notes |
|------|------|-------------------|-------|
| #8 AI Search | C + S2 | `ai-search-intelligence-pack` / `ai_search_install.py` | Brand Radar + Finseo BYO + `ai_visibility_ui` v1–v3 |
| #9 Finance | F3 | `finance-intelligence-pack` / `finance_install.py` | Live activation HOLD (STA-312 pattern) |
| #10 HR | H3 | `hr-talent-intelligence-pack` / `hr_talent_install.py` | Live activation HOLD |

Stop-lines: raw AI answers / payroll-banking / employee+compensation PII → Memory/KG blocked; no LinkedIn scrape.

---

## Explicit non-goals (this spike)

- Tip smoke / live prod evidence for Pack #8 (**build follow-on**)  
- Deep Plaid Link / Gusto partner OAuth live tests (Finance/HR HOLD)  
- Compliance / Business OS unchanged  
- First-party multi-model BYO path **D**  
- Peec / Profound enterprise sales motions

---

## Finance / HR — **LOCKED** (Cesar 2026-07-15; historical options retained)

| Choice | Meaning |
|--------|---------|
| **F3** | All Finance live — QB + Xero + NetSuite + Plaid if entitled ← **SELECTED** (scaffold; live HOLD) |
| **H3** | All HR live — Workday + BambooHR + Greenhouse + Gusto ← **SELECTED** (scaffold; live HOLD) |

### Finance (#9) — options (historical)

| Choice | Meaning |
|--------|---------|
| **F0 — Hold** | No Finance intelligence pack |
| **F1 — Scaffold only** | Catalog + mocked Cash Flow agent |
| **F2 — Smoke QB only** | Live QuickBooks on smoke org only |
| **F3 — All Finance live** | ← **SELECTED** |

### HR & Talent (#10) — options (historical)

| Choice | Meaning |
|--------|---------|
| **H0 — Hold** | No HR intelligence pack |
| **H1 — Scaffold only** | Catalog + mocked Recruiting agent |
| **H2 — ATS only (Greenhouse)** | Live Greenhouse on smoke org |
| **H3 — All HR live** | ← **SELECTED** |

---

## Handoff after research (not part of this spike)

1. ~~Cesar picks API A–E and scrape S0–S2~~ — **done (C + S2)**  
2. ~~Cesar picks Finance F0–F3 and HR H0–H3~~ — **done (F3 + H3; live HOLD)**  
3. **Build follow-on:** Pack #8 tip smoke → `docs/delivery/phase4-ai-search-pack-live.json` (Ahrefs and/or Finseo invoke + optional UI capture); update master program row when tip PASSes.  
4. Do **not** reopen vendor research unless tip is blocked by missing Brand Radar / Finseo entitlement on smoke org.

---

## Evidence / provenance

- Phase 0 vision: `docs/delivery/phase0-twelve-pack-marketplace-vision.md` (AI Visibility NEW)  
- Scrape path S0–S2 added per Cesar 2026-07-15  
- Path lock: Cesar **C + S2** (2026-07-15)  
- Program: `docs/delivery/master-knowledge-intelligence-packs-program.md` row 8  
- Marketing pattern: `marketing_install.py`, `auth_mode.py` (`ahrefs` BYO), Pack KPI Phase 3.5  
- Scaffold on `main`: `ai_search_install.py`, `ahrefs_tools` Brand Radar, `finseo` / `ai_visibility_ui` catalogs  
- API docs re-verified 2026-07-17 (Ahrefs Brand Radar overview family; Finseo `/v1` projects/metrics/prompts)  
- Finance/HR: STA-312-class governance (live connect HOLD)

---

## Sign-off (research)

| Field | Value |
|-------|-------|
| Artifact | `docs/delivery/phase8-ai-search-research-spike.md` |
| Research status | **DONE** (2026-07-17) |
| Locked path | **C + S2** (v1/v2/v3) |
| Owner | Cesar / program |
| Next gate | Pack tip smoke (build), not research |
