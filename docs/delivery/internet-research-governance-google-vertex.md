# Internet research — governance: Google Cloud path vs Tavily

**Date:** 2026-07-18  
**Status:** Recommendation recorded — **`INTERNET_RESEARCH_ENABLED` stays OFF** until owner sign-off + pricing estimate + integration work  
**Program context:** [`adaptive-retrieval-layer-program.md`](./adaptive-retrieval-layer-program.md)

This document captures the cost-effective governance path for live internet research in Gravitree assistant retrieval. It supersedes “wait for Tavily Enterprise only” as the sole viable option, without authorizing enablement in production.

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

1. **Reuse GCP footprint.** GSC OAuth work ([`marketing-phase0-gsc-oauth.md`](./marketing-phase0-gsc-oauth.md)) already uses shared `GOOGLE_OAUTH_CLIENT_ID` / Google Cloud project patterns. Vertex grounding likely extends an existing GCP project rather than a net-new vendor relationship.

2. **Use correct product names** when provisioning (see Option 2 above). Reject Custom Search JSON API references in older docs.

3. **Know standard-tier guarantees before enablement:**
   - No training without permission (Training Restriction).
   - ~30-day debug retention (not indefinite; not for training).
   - SOC 2 / standard Cloud DPA — not “call sales for basic DPA.”

4. **Pricing — open item (not yet a go/no-go PASS):** Pull **current** list prices and estimate against realistic assistant internet-query volume. List prices move; verify on [Agent Search / Vertex AI App Builder pricing](https://cloud.google.com/generative-ai-app-builder/pricing) at decision time.

   **Indicative reference only (verify before commit):**

   | Path | Approx. list (USD) | Notes |
   |------|-------------------|--------|
   | Vertex AI Search — data store query | ~$4 / 1k queries | Customer-indexed RAG, not live open web |
   | Grounding with Google Search (Gemini 2.x) | ~$35 / 1k grounded queries; first 10k/day/account sometimes free | Live web — closest Tavily replacement |
   | Grounding with Google Search (Gemini 3) | Per **search query** model generates (multi-query prompts bill multiple) | See [Gemini grounding docs](https://ai.google.dev/gemini-api/docs/google-search) |

   Structural win: **usage-based API billing**, not a flat ~$49k/yr enterprise search contract — but **real dollars depend on volume and which grounding SKU is chosen**.

5. **Engineering follow-up (when authorized):** Abstract `web_research.py` behind a provider interface; add Google grounding provider; keep Tavily as fallback or remove after cutover; gate on `INTERNET_RESEARCH_ENABLED` + governance sign-off.

---

## Decision matrix (where this leaves options)

| Option | Governance (standard tier) | Cost shape | Status for Gravitree |
|--------|---------------------------|------------|----------------------|
| **Tavily default API** | Weak (training/retention concerns) | Low per-query self-serve | **Current code path; stay OFF** |
| **Tavily Enterprise** | Stronger (zero-retention marketed) | High flat enterprise | **Out of budget** — not pursued |
| **Exa standard** | Weak (same enterprise upsell pattern) | Self-serve | Not integrated |
| **Perplexity Sonar** | Separate review needed | Paid API | Not integrated |
| **Google Cloud — Vertex / Search grounding** | **Stronger baseline (no training on paid standard)**; 30-day debug retention; zero-retention via DPA add-on | Usage-based GCP | **Recommended replacement candidate** — pricing + integration TBD |

**Recommendation:** Treat **Google Cloud Vertex / Search grounding** as the **likely replacement** (or parallel) for Tavily for internet research — **better governance default on standard paid terms**, **without** requiring Tavily Enterprise — subject to:

- [ ] Named owner written sign-off (same bar as STA-312 / Memory Option B — schema-ready ≠ authorized).
- [ ] Pricing estimate vs expected query volume on the **specific** grounding SKU.
- [ ] Integration + prod smoke with `INTERNET_RESEARCH_ENABLED` still gated.

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
