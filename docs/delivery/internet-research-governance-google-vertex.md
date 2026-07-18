# Internet research — governance: Google Cloud path vs Tavily

**Date:** 2026-07-18  
**Status:** **CLOSED (governance track)** — recommendation recorded; **`INTERNET_RESEARCH_ENABLED` stays OFF** until owner go/no-go + integration  
**Program context:** [`adaptive-retrieval-layer-program.md`](./adaptive-retrieval-layer-program.md)

This document captures the cost-effective governance path for live internet research in Gravitree assistant retrieval. It supersedes “wait for Tavily Enterprise only” as the sole viable option, without authorizing enablement in production.

**Closure artifact:** [`internet-research-governance-closure.json`](./internet-research-governance-closure.json)

---

## Current production state (unchanged)

| Item | State |
|------|--------|
| `INTERNET_RESEARCH_ENABLED` | **OFF** |
| Live provider | **Tavily only** — `backend/app/services/web_research.py` → `https://api.tavily.com/search` |
| Milestone 2 evidence | Internal-only probes: `internet_ran: false` @ prod `9d1ae051` |

No code or flag change is implied by this document alone.

---

## Two Google options — only one is real

### Option 1: Custom Search JSON API — **ruled out**

- Familiar “Google Search API” from tutorials and Stack Overflow.
- **Closed to new customers**; Google has announced **discontinuation January 1, 2027**.
- Do not build new infrastructure here regardless of nominal cost.

### Option 2: Vertex AI Search / Google Search grounding — **correct forward path**

- Generally available **paid Google Cloud API** (not a special enterprise-only sales product).
- Endpoint family: **`discoveryengine.googleapis.com`** (Vertex AI Search / “Agent Search” in current docs).
- For **live public web** (Tavily-equivalent), the relevant capability is **Grounding with Google Search** on Vertex/Gemini — distinct from search over a customer-indexed data store, but same GCP project, billing, and terms surface.

**Integration note for engineering:** Confirm product at build time:

- **Live web grounding** → Grounding with Google Search (Gemini / Vertex grounding APIs).
- **Search over indexed corpus** → Vertex AI Search data-store queries (~$4 / 1k queries on standard search tier — see pricing section).

Do **not** wire the deprecated Custom Search JSON API.

---

## Which Google product replaces Tavily? (read this before pricing)

Gravitree’s internet-research use case is **“answer using current web information”** — live retrieval from the public web, like Tavily today. That is **not** the same as querying a Vertex AI Search **data store** you indexed yourself.

| Google product | What it does | Replaces Tavily? |
|----------------|--------------|------------------|
| **Grounded Generation — grounding on Google Search** | Live public-web search + grounded answer generation (Vertex/Gemini Grounded Generation API) | **Yes — this is the Tavily-equivalent** |
| Agent Search — Standard / Enterprise edition queries | Semantic search over **your** indexed documents, website crawl, or structured data in a data store | **No** — internal/corpus RAG, not live open web |
| Custom Search JSON API | Legacy programmable search | **No** — ruled out (EOL) |

**Do not** use Agent Search **$4 / 1k** (Enterprise) or **$1.50 / 1k** (Standard) data-store query pricing when estimating Tavily replacement cost. Those SKUs bill **retrieval from indexed content**, not live web grounding.

Tavily today: `backend/app/services/web_research.py` posts the user query to Tavily and returns titles/URLs/snippets. The Google analogue is **Grounding with Google Search** under [Grounded Generation API pricing](https://cloud.google.com/generative-ai-app-builder/pricing) (Example #2 on that page).

---

## Why this matters for governance (the Tavily/Exa comparison)

The due-diligence question for any vendor is unchanged:

1. What query/content is sent externally?
2. Retention and training use?
3. Is a defensible enterprise policy available **without** a large custom contract?

### Tavily and Exa (standard / self-serve tiers)

- **Training / improvement:** Standard API terms allow vendor (and, for Tavily, third-party index/AI providers) to use submitted queries for model improvement unless upgraded.
- **Zero retention / no-training at contractual strength:** Typically requires **paid enterprise** negotiation (Tavily ~$49k/yr AWS Marketplace tier cited in prior briefing; Exa similar enterprise gating).

### Google Cloud (standard paid project — billing enabled)

- **Training Restriction (Service Specific Terms):** Google will not use customer data to train or fine-tune AI/ML models **without prior permission or instruction** — baseline on ordinary paid GCP/Vertex use, not a separate enterprise upsell for that specific claim.
- **Retention (honest caveat):** Standard tier is **not** zero-retention. Vertex AI Search / grounding paths retain query-related data **up to 30 days for debugging**, not for training. **True zero-retention** still requires Google Cloud sales + **DPA add-on** (same *class* of enterprise gate as Tavily/Exa for zero-retention, but the **no-training baseline is already stronger** on standard paid GCP).

- **Compliance surface:** SOC 2, existing Google Cloud DPA infrastructure for paying customers.

**Summary:** With Tavily/Exa, “no training on your data” is an upsell. With Google Cloud paid standard terms, **no training is already contractual baseline**; zero-retention is the optional upsell.

---

## Practical path for Gravitree

1. **Reuse GCP footprint — same project, not just same vendor.**

   Gravitree uses **one Google Cloud project** hosting the **“Gravitre OAuth”** OAuth 2.0 client (`GOOGLE_OAUTH_CLIENT_ID` / `SECRET`) for login (Supabase) and all Google connectors — see [`docs/integration/GOOGLE_OAUTH.md`](../integration/GOOGLE_OAUTH.md) and [`CONNECTOR_IMPLEMENTATION_MATRIX.md`](../CONNECTOR_IMPLEMENTATION_MATRIX.md) (“One Google Cloud project → one OAuth 2.0 Client ID”).

   GSC OAuth (Search Console API, `webmasters.readonly`, redirect on that client) was enabled on **that same project/client** — [`marketing-phase0-gsc-oauth.md`](./marketing-phase0-gsc-oauth.md).

   Vertex / Discovery Engine / Grounding with Google Search should be provisioned in **the same GCP project** (identify via OAuth client ID → APIs & Services → Credentials in console). That is literally the same project and billing account, not a separate GCP org — unless Gravitree deliberately chooses a second project later (not the current architecture).

   Additional work in that project: enable Vertex AI / Discovery Engine / grounding APIs + service account or workload identity for server-side calls (distinct from user OAuth tokens used for GSC connector reads).

2. **Use correct product names** when provisioning (see product table above). Reject Custom Search JSON API references in older docs.

3. **Know standard-tier guarantees before enablement:**
   - No training without permission (Training Restriction).
   - ~30-day debug retention (not indefinite; not for training).
   - SOC 2 / standard Cloud DPA — not “call sales for basic DPA.”

4. **Pricing — Tavily-equivalent product (VERIFIED list price; volume estimate NOT RUN)**

   **Source:** [Agent Search / Grounded Generation pricing](https://cloud.google.com/generative-ai-app-builder/pricing), **Grounded Generation — Example #2: Grounding on Google Search**, fetched **2026-07-18**.

   | Line item | List price (USD) | Applies to Tavily replacement? |
   |-----------|------------------|--------------------------------|
   | **Grounded Generation for grounding on Google Search** | **$0.00 / 1k count** for counts **0–10,000 per day per account**; **$35.00 / 1k count** for counts **above 10,000 per day per account** | **Yes — this line item** |
   | Agent Search Enterprise edition query | $4.00 / 1k query | **No** — indexed data store |
   | Agent Search Standard edition query | $1.50 / 1k query | **No** — indexed data store |

   **Additional costs (not in table above):** Gemini model input/output tokens for the grounded generation call are billed separately at the selected model’s rate. Example #2 on the pricing page totals ~**$35.14 / 1k requests** at volume **above** the daily free grounding tier, mostly from the Google Search grounding line item plus Flash token charges.

   **Free tier (verified):** First **10,000** grounding-on-Google-Search **counts per day per account** are **$0** for the grounding surcharge. This is **per day**, not per month.

   **Volume calculus at Gravitree expected query volume: NOT RUN.** No documented forecast of daily `internet_research` / `search_web` invocations when the flag is enabled. Qualitative note only: early prod with `INTERNET_RESEARCH_ENABLED` off and internet stage gated would likely sit **under 10k grounding counts/day** initially → **$0 grounding surcharge** on that line item, but Gemini token costs still apply. Above 10k/day/account, marginal grounding cost is **$35 per additional 1,000 counts per day**. Owner should model volume before go/no-go.

   **Pricing go/no-go:** List price for the **correct** product is verified; **cost PASS for enablement** still requires owner volume estimate — explicitly **NOT RUN** here.

5. **Engineering follow-up (when authorized):** Abstract `web_research.py` behind a provider interface; add Google **Grounding with Google Search** provider; keep Tavily as fallback or remove after cutover; gate on `INTERNET_RESEARCH_ENABLED` + governance sign-off.

---

## Decision matrix (where this leaves options)

| Option | Governance (standard tier) | Cost shape | Status for Gravitree |
|--------|---------------------------|------------|----------------------|
| **Tavily default API** | Weak (training/retention concerns) | Low per-query self-serve | **Current code path; stay OFF** |
| **Tavily Enterprise** | Stronger (zero-retention marketed) | High flat enterprise | **Out of budget** — not pursued |
| **Exa standard** | Weak (same enterprise upsell pattern) | Self-serve | Not integrated |
| **Perplexity Sonar** | Separate review needed | Paid API | Not integrated |
| **Google Cloud — Grounding with Google Search** | **Stronger baseline (no training on paid standard)**; 30-day debug retention; zero-retention via DPA add-on | Usage-based; **$35/1k grounding counts/day above 10k free tier** (+ model tokens) | **Recommended Tavily replacement** — governance closed; enablement not authorized |

**Recommendation:** Treat **Grounding with Google Search** (Grounded Generation API) as the **likely replacement** for Tavily — **not** Agent Search data-store query SKUs. Better governance default on standard paid terms, without Tavily Enterprise pricing — subject to **all three enablement gates** (governance, volume, metering):

- [x] Governance track closed (2026-07-18) — **not** the same as flipping the flag.
- [ ] **Volume-based cost estimate** at enablement time (**NOT RUN** in this closure).
- [ ] **Metering / credit pass-through with margin** tied to existing plan-tier usage infrastructure (**NOT BUILT** — named precondition; see § below).
- [ ] Integration + prod smoke before `INTERNET_RESEARCH_ENABLED=true`.

---

## Metering — separate enablement gate (NOT BUILT)

Grounding costs scale with usage ($35/1k above Google’s 10k/day/account free tier, plus Gemini tokens). **“Governance says this is safe” ≠ “we will not lose money on it.”** Internet research must not ship to real customers without a pass-through mechanism.

### What exists today (repo audit 2026-07-18)

| Primitive | Status | Internet research? |
|-----------|--------|--------------------|
| `usage_tracking` — `ai_credits`, `workflow_runs`, `operator_usage`, `rag_usage` | **Live** (`backend/app/billing/service.py`) | **No** — `web_research.py` does not call `record_usage` |
| `ai_credits` on Node / Control / Command + Stripe Billing Meter | **Live** when metered price IDs configured (`stripe_metering.py`) | **Partial** — LLM tokens only; **grounding surcharge is a separate Google line item** |
| `intelligence_usage_logs` (Intelligence Pack per-request logging) | **Not built** — scoped in Phase 0 MSP docs, **no table in repo** | Pack-specific; would need extension for non-pack grounding calls |

**Engineering recommendation (Decision A — when gate 3 opens):** Extend existing `usage_tracking` / **`ai_credits`** spine; record each grounding call (count + token metadata); map Google cost → credits with margin; wire to Stripe meter. **Do not invent a third customer-facing unit.**

### Pricing model (Decision B — direction recorded; numbers pending gate 2)

Separate from the engineering primitive choice. **Direction recorded 2026-07-18** — specific allotments sized only after gate 2 (volume estimate).

**Rejected — flat per-plan dollar inclusion, signup free-credit pool:**

- Flat $35/month baked into tier: skewed usage, inverted margin (see prior section).
- **Signup-triggered free credits** (e.g. “500 free API calls”): second allotment mechanism alongside plan-tier `ai_credits` — overlaps the one-concept rule; not used here.

**Recorded direction — plan-tier included allotment (not signup):**

Framing: **“how much research is included in what you’re already paying for”** — not a free-trial research pool.

| Tier | Direction |
|------|-----------|
| **Node** | None or very small taste (handful/month) — discoverable, limits exposure on entry tier |
| **Control** | Modest included allotment — sized post–volume estimate; “included with your plan” |
| **Command** | Larger allotment — aligned with Command’s broader Intelligence Pack access |
| **Overage** | General **`ai_credits` pool** on any tier — same as all other usage |

Avoids: first-try hard wall (something at every tier) **and** unbounded free usage before data to size responsibly.

**Still open until gate 2:** Numeric allotments per tier, conversion rate + margin over Google $35/1k, optional research line item in usage UI (same currency).

**Owner still must decide before build:**

1. ~~Tier allotment shape~~ — **recorded**; numbers TBD after volume estimate.
2. Grounding → `ai_credits` conversion rate and margin.
3. Boundary UX when included allotment exhausted (charge from general pool with notice — align with existing overage).

### Sequencing

**Do not build metering infrastructure now.** Flag stays off; volume estimate is NOT RUN. Gate 3 scoped only when seriously considering enablement. Pricing direction is recorded; **committing to specific numbers waits on gate 2**.

---

## Governance track closure (2026-07-18)

| Item | Status |
|------|--------|
| Candidates evaluated | Tavily default, Tavily Enterprise, Google Vertex/Grounding, Custom Search JSON (ruled out) |
| Recommended path | Grounding with Google Search on existing Gravitre GCP project |
| Training / retention posture | Documented; no-training ≠ zero-retention caveat preserved |
| Tavily-equivalent list pricing | **VERIFIED** @ 2026-07-18 from Google pricing page (see §4) |
| Gravitree volume cost model | **NOT RUN** |
| Metering / credit pass-through | **NOT BUILT** — named enablement precondition (see Metering section) |
| `INTERNET_RESEARCH_ENABLED` | **OFF** |
| Retrieval-layer program | **Separate; closed** — does not block this governance close |

**Verdict:** Governance track **closed**. Enablement requires **three gates:** (1) governance ✓, (2) volume estimate, (3) metering with margin — only (1) is done.

---

## What this does **not** change

- Adaptive retrieval layer program: **closed**; Milestone 2 latency gap unchanged.
- Milestone 1 / Research Manager: **PASS**, unaffected.
- **`INTERNET_RESEARCH_ENABLED`:** remains **OFF** until the items above are satisfied.

---

## References

- Gravitree Tavily integration: `backend/app/services/web_research.py`
- Config gate: `INTERNET_RESEARCH_ENABLED` in `backend/app/config.py`
- [Google Cloud Generative AI App Builder / Agent Search pricing](https://cloud.google.com/generative-ai-app-builder/pricing)
- [Grounding with Google Search (Gemini API)](https://ai.google.dev/gemini-api/docs/google-search)
- [Google Cloud Service Specific Terms](https://cloud.google.com/terms/service-terms) — Training Restriction
- Prior program closure: `docs/delivery/adaptive-retrieval-layer-program.md`
