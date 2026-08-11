# Research Lookups COGS & pricing diagnosis

**Status:** Diagnosis only — no pricing / copy / plan changes in this pass  
**Date:** 2026-08-11  
**Prod tip:** `93bac82e` (`internet_research_enabled=true`, `web_research_provider_configured=true`)  
**Evidence bar:** Same as voice COGS work (`$0.02645/min` blended). Every claim is **CONFIRMED** or **UNKNOWN**.

Companion voice reference: `docs/delivery/realtime-voice-agent-phases-0-7.md` (blended duplex minute **$0.02645**).

---

## Executive recommendation

**Keep Research Lookups transparent and metered** (included allotment + visible overage). Do **not** fold/hide it the way voice was.

That is not because current COGS is high — observed usage is tiny and current COGS is near **$0**. It is because:

1. **Live provider path today is Tavily** (all metered rows), at published **~$0.008/lookup** (basic search, 1 credit) — not the same “structurally capped by conversation minutes” profile as voice.  
2. **Intended primary path is Google Grounding on `gemini-2.5-flash`**, where paid grounding is **$35 / 1,000 prompts** after a shared free RPD allowance — **$0.035/lookup** once the platform free tier is exhausted.  
3. **Real customer usage is not yet informative** (35 lifetime lookups; max **17/org/month**, almost all smoke org). There is no evidence of a heavy tail *yet*, but also no evidence it will stay empty — research can scale for competitive/due-diligence use without a natural per-session minute ceiling.  
4. Hiding an uncapped meter before real demand arrives would reverse the voice lesson: voice was hidden only after COGS was proven trivial **and** usage shape was bounded.

Equally legitimate outcome: keep the hybrid model Cesar already signed (10 / 60 / 200 included, **$0.35** overage).

---

## Part A — Live provider and real cost

### A1. Which API does Research Lookups call?

| Layer | Finding | Status |
| -- | -- | -- |
| Code primary | `WEB_RESEARCH_PROVIDER` default **`google`** → `search_google_grounding` (`gemini-2.5-flash` + `GoogleSearch` tool) | **CONFIRMED** `web_research.py`, `web_research_google.py`, `config.py` |
| Code fallback | Tavily `POST https://api.tavily.com/search` (`include_answer: false`, basic depth) when Google fails / not configured / `provider=tavily` | **CONFIRMED** |
| Prod health | `internet_research_enabled=true`, `web_research_provider_configured=true` @ tip `93bac82e` | **CONFIRMED** |
| Metered usage `metadata.provider` | **100% `tavily`** (35/35 rows) — zero `google_grounding` rows in `usage_records` | **CONFIRMED** DB query 2026-08-11 |
| Prior live smoke | `internet-research-live-preflag.json` / go-live: provider **`tavily`** fallback when Google unavailable | **CONFIRMED** artifact |

**Verdict:** Product design is Google-primary; **every billed/metered lookup so far executed on Tavily.** Google path is real code but not represented in usage_records yet.

### A2. Account-level per-query cost

#### Tavily (actual path in usage_records)

| Item | Number | Status |
| -- | -- | -- |
| Code call shape | Basic search, `include_answer=false` → **1 API credit** | **CONFIRMED** code + [Tavily credits docs](https://docs.tavily.com/documentation/api-credits) |
| Published PAYG | **$0.008 / credit** | **CONFIRMED** published list (2026-08-11 fetch) |
| Published plan rates | $0.0075 → $0.005 / credit (Project→Growth) | **CONFIRMED** published list |
| Gravitre Tavily **account** plan / invoice | Not readable from this environment (no dashboard/MCP billing access) | **UNKNOWN** — use PAYG **$0.008** as conservative published bound |

#### Google Grounding (intended primary, `gemini-2.5-flash`)

| Item | Number | Status |
| -- | -- | -- |
| Model | `gemini-2.5-flash` (`WEB_RESEARCH_GOOGLE_MODEL`) | **CONFIRMED** settings default |
| Grounding free (paid tier) | **1,500 RPD** free (shared with Flash-Lite), then **$35 / 1,000 grounded prompts** = **$0.035 / lookup** | **CONFIRMED** [Gemini API pricing — Gemini 2.5 Flash](https://ai.google.dev/gemini-api/docs/pricing) |
| Token rates (paid) | Input **$0.30 / 1M**, output **$2.50 / 1M** | **CONFIRMED** same page |
| Gravitre GCP/Gemini **invoice** line | Not pulled this pass | **UNKNOWN** account invoice; list prices used |

Internal safety constant still documents paid-tier grounding as `$0.035`:  
`ESTIMATED_GROUNDING_COGS_USD_PER_LOOKUP_AT_PAID_TIER = 0.035` in `research_lookup_metering.py` — **CONFIRMED**.

### A3. Blended cost per lookup (secondary costs)

| Cost component | Tavily path (live metered) | Google path (code primary) |
| -- | -- | -- |
| Search / grounding surcharge | ~**$0.008** (1 credit PAYG) | **$0** under 1,500 RPD free; else **$0.035** |
| Provider LLM summarization | **$0** — `include_answer=false` | Included in Gemini call |
| Gemini tokens | N/A | Short prompt + `max_output_tokens=512` → order **~$0.0001–$0.001** at $0.30/$2.50 per 1M |
| Debited to AI Credits pool? | No separate research→ai_credits mapping in `web_research*` | **CONFIRMED none** — grounding tokens are **not** written to `ai_credits` / `model_calls` from this path |

**Blended (honest):**

| Scenario | Blended COGS / lookup |
| -- | -- | --- |
| Current live (Tavily, PAYG bound) | **≈ $0.008** |
| Google under free RPD | **≈ token-only (~$0.001)** → treat as **≈ $0.001** |
| Google past free RPD | **≈ $0.035 + ~$0.001 ≈ $0.036** |

Customer overage list price remains **$0.35 / lookup** (code fallback + marketing constants). Margin vs Tavily PAYG ≈ **43×**; vs Google paid grounding ≈ **10×**.

**Customer-facing allotments (code fallback / marketing):** Node **10**, Control **60**, Command **200**, overage **$0.35**.  
**DB drift (fixed 2026-08-11):** live `billing_plans.features` was missing `research_lookups_per_month` / `research_lookup` overage (voice minutes present). Root cause: `20260729120000_seed_all_billing_plans.sql` **replaced** `features`/`overage_rates` wholesale without research keys after `20260719120000` had merged them. Runtime fell back to code constants — same class as prior Node/Command display bugs. Restored via `20260811120000_restore_billing_plans_research_lookups.sql` + live apply; seed/ON CONFLICT hardened to **merge**.

---

## Part B — COGS at allotments and real usage

### B1. Monthly COGS at full included burn (per org)

Using **Tavily PAYG $0.008** (matches live provider in usage_records) and **Google paid $0.035** (worst-case primary path):

| Tier | Included lookups | COGS @ Tavily $0.008 | COGS @ Google paid $0.035 | vs plan price* |
| -- | -- | -- | -- | -- |
| Node | 10 | **$0.08** | **$0.35** | vs ~$49 |
| Control | 60 | **$0.48** | **$2.10** | vs ~$129 |
| Command | 200 | **$1.60** | **$7.00** | vs ~$299 |

\*Tier list prices from earlier research-lookups phase0 audit ($49 / $129 / $299) — **CONFIRMED** prior artifact; not re-fetched from Stripe this pass.

Voice comparison (included minutes × $0.02645): Node 60×$0.02645 ≈ **$1.59**, Control 300 ≈ **$7.94**, Command 1200 ≈ **$31.74**.  
Research at Command full burn on Tavily (**$1.60**) is similar to Node voice; on Google paid (**$7**) it is closer to Control voice — still small vs plan price, but **not** “more trivial than voice” across the board.

### B2. Real usage patterns

`usage_records` where `metric_type='research_lookups'` (2026-08-11):

| Metric | Value | Status |
| -- | -- | -- |
| Lifetime rows / quantity | **35** | **CONFIRMED** |
| Distinct orgs | **2** | **CONFIRMED** |
| Provider mix | **tavily 100%** | **CONFIRMED** |
| By month | 2026-07: 18 · 2026-08: 17 | **CONFIRMED** |
| Org-month max | **17** (isolated smoke org `f07e57c0…`) | **CONFIRMED** |
| Org-month median | **17** (n=3 org-months) | **CONFIRMED** (tiny n) |
| Operator org (`cbbf993b…`) | **1** lifetime lookup | **CONFIRMED** |
| Stripe reported overage | **0** rows with `stripe_reported_at` | **CONFIRMED** |

**Honest read:** There is **no real customer heavy-usage distribution** yet. Median/max are smoke-dominated. You **cannot** justify a hide decision from “usage shows the tail is empty” — the sample is too small and non-representative.

**Structural heavy-user check (not observed, but the risk that differs from voice):**  
10,000 lookups/month on one power org ≈ **$80** Tavily PAYG or **$350** Google paid grounding. That is a material uncapped cloud bill if Research Lookups were absorbed into flat plans with no meter. Voice minutes are naturally bounded by human conversation time; research is not.

---

## Part C — Recommendation (evidence-based)

### Keep metered + transparent (recommended)

| Reason | Evidence |
| -- | -- |
| Live path is already a per-call vendor | All 35 metered lookups = Tavily |
| Google paid grounding is not “voice-trivial” | $0.035/lookup list after free RPD |
| Usage data cannot clear the heavy-tail risk | Smoke-only, max 17/org/month |
| Hybrid model already signed | Cesar allotment sign-off 2026-07-23 (10/60/200 + $0.35) |
| Circuit breaker exists but is ops, not pricing | Hourly org limit (default 500) — caps abuse, does not replace overage honesty |

### When a voice-like hide *would* become defensible (not now)

Only if **all** of the following become CONFIRMED:

1. Sustained real-customer usage with p95 still near allotment (or well under Google free RPD **platform-wide**).  
2. Account invoices show actual Tavily/Google spend matching the “near-zero” thesis for 1–2 billing cycles.  
3. Product accepts a hard admin/org cap so “hide” cannot become uncapped Google $0.035 / Tavily $0.008 burn.  
4. `billing_plans` research keys restored so allotments remain a real DB SoT.

Until then, hiding would be an assumption — the opposite of the voice decision process.

### Not recommended

- Treating Research Lookups as “same as voice → hide” because current smoke COGS is ~$0.  
- Raising customer overage without new COGS evidence ($0.35 already ≫ $0.008–$0.035).  
- Assuming Google is the live cost base while usage_records say Tavily.

---

## Follow-up (2026-08-11) — dual provider + billing_plans restore

### Why Gemini grounding exists when traffic is 100% Tavily

**Not dead code. Deliberate dual-provider design that has never won in prod.**

| Fact | Evidence |
| -- | -- |
| Governance chose Google Grounding as Tavily *replacement* (training/retention) | `internet-research-governance-closure.json` — recommended_replacement = Grounded Generation |
| Code default `WEB_RESEARCH_PROVIDER=google`, Tavily = fallback (`WEB_RESEARCH_FALLBACK_TAVILY=true`) | `config.py`, `web_research.py` |
| Live smoke still sets provider=google but metered result = tavily | `internet-research-live-latest.json` — `web_research_provider: google`, `external_search.provider: tavily`; pre-go-live: “Google primary fell back to Tavily” |
| Lifetime usage_records | 35/35 `provider: tavily`, 0 `google_grounding` |

**Honest read:** Google is the *intended* primary cost path; Tavily is the *actual* production path because Google fails or returns no results and fallback always wins. That is an unexplained live gap (credentials / API / empty grounding chunks), not a second product surface by design. `web_research_provider_configured=true` can be true from Tavily alone — it does not prove Google works.

**Consolidation recommendation (ops, not this pricing pass):** Until a live lookup meters `google_grounding`, set prod `WEB_RESEARCH_PROVIDER=tavily` so the configured default matches reality (one billing surface). Keep Google code behind explicit opt-in until a PASS smoke records `provider=google_grounding`. Do **not** treat Google as a live COGS base while traffic is 100% Tavily. Removing Google entirely is a product/governance call — only after abandoning the closed governance recommendation.

### billing_plans research keys — fixed

| Step | Result |
| -- | -- |
| Root cause | `20260729120000_seed_all_billing_plans.sql` `ON CONFLICT` **replaced** features/overage_rates without research keys (after `20260719120000` had merged them). Voice survived via later merge migration. |
| Live restore | 2026-08-11 — node 10 / control 60 / command 200 / enterprise 200; overage `research_lookup=0.35`; voice keys intact (`VERIFY_PASS`) |
| Repo harden | New migration `20260811120000_…`; seed + seed_all now include research+voice keys; ON CONFLICT **merges** jsonb instead of replace |

---

## Open UNKNOWNs (do not invent)

1. Gravitre’s **Tavily account plan** and invoice unit price (vs published $0.008).  
2. Whether Railway currently has a working **GEMINI_API_KEY** (health says configured; usage never records `google_grounding`).  
3. Google Cloud / AI Studio **invoice** grounding line for this project.  
4. Real paying-customer research distribution (needs more than smoke org).  
5. ~~Why `billing_plans` lost research keys~~ — **ANSWERED 2026-08-11:** wiped by `20260729120000` wholesale features replace; restored live + hardened seeds.

---

## Appendix — math scratch

```
Voice included COGS (reference): minutes × $0.02645
  Node 60 → $1.587
  Control 300 → $7.935
  Command 1200 → $31.74

Research included COGS (Tavily $0.008):
  Node 10 → $0.08
  Control 60 → $0.48
  Command 200 → $1.60

Research included COGS (Google paid $0.035):
  Node 10 → $0.35
  Control 60 → $2.10
  Command 200 → $7.00

Customer overage: $0.35 / lookup (list)
```

---

## Update discipline

Append dated sections when account invoices or real-customer usage arrive. Do not upgrade UNKNOWN → CONFIRMED without invoice / DB / tip evidence pointers.
