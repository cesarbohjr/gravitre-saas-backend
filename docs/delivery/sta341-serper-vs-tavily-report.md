# STA-341 — Tavily consolidation + Serper evaluation

**Date:** 2026-08-11  
**Linear:** [STA-341](https://linear.app/staqbot/issue/STA-341)  
**Pricing model:** unchanged (included allotments + transparent $0.35 overage)

---

## Step 1 — Tavily consolidation (PASS)

| Check | Result | Evidence |
| -- | -- | -- |
| Railway `WEB_RESEARCH_PROVIDER` | **`tavily`** (explicit) | `railway variables --kv` 2026-08-11 |
| Prod health | `internet_research_enabled=true`, `web_research_provider_configured=true` | `git_sha=b56326119b1c99100d0557ffe9ad4e34aa5d9f7e` @ health `2026-08-11T08:26:25Z` |
| Settings under Railway env | `web_research_provider=tavily` | `railway run` → `verify-web-research-provider-tavily-live.py` |
| Google primary block entered? | **No** | `path_analysis.google_primary_block_entered=false` |
| Live lookup provider | **`tavily`** | `external_search.provider=tavily`, `totalResults=3` |
| Metered `usage_records` | **`provider=tavily`** | row `@ 2026-08-11T08:25:41.503657Z` org `f07e57c0…` |

Artifact: `docs/delivery/web-research-provider-tavily-live.json`  
Verdict: **PASS — direct Tavily path; not primary-then-fallback.**

Config-only change (no code deploy required). Live tip remains `b5632611` (docs/follow-up commits after that do not affect provider selection).

---

## Step 2 — Serper vs Tavily

### 2A. Real, current Serper pricing (official page)

Source: **https://serper.dev/** homepage “Simple, Affordable Pricing” (fetched/screenshot 2026-08-11). Prepaid credits, 6-month validity, no monthly subscription. Free: **2,500** queries (no card).

| Pack | Price | Credits | USD / query (1 credit, ≤10 results) |
| -- | -- | -- | -- |
| Starter | $50 | 50k | **$0.001** |
| Standard | $375 | 500k | **$0.00075** |
| Scale | $1,250 | 2.5M | **$0.0005** |
| Ultimate | $3,750 | 12.5M | **$0.0003** |

vs Tavily basic search published PAYG bound **~$0.008/query** (prior COGS diagnosis). Serper Starter ≈ **8× cheaper**; Ultimate ≈ **27× cheaper**.

No Gravitre Serper **account invoice** yet (no key in Railway). List prices above are from Serper’s own site, not blogs.

### 2B. Historical query sample (honest scope)

`usage_records` store `source_id` hashes only — no plaintext. Distinct real research-path queries recovered:

1. `What is the current US federal funds rate?` — internet-research live + Step 1 verify  
2. `Summarize what you can find about our refund policy…` — research-cascade smoke + repeated `conversation_messages`

**n=2 distinct** (all other research lookups are repeats of these smokes). Sample is sparse but real — not invented SEO fluff.

### 2C. Side-by-side quality

| Query | Tavily (top URLs / signal) | Serper (top URLs / signal) | Quality hold? |
| -- | -- | -- | -- |
| Federal funds rate | NY Fed EFFR, NerdWallet, TradingEconomics, FRED; snippets cite **3.50–3.75%** / EFFR **3.63%** | NY Fed EFFR, Fed explained, NerdWallet, TradingEconomics; same target range **3.50–3.75%** | **Yes** — authoritative overlap |
| Refund policy | TermsFeed, IgMin, BecomingMinimalist, Termly, Influx | TermsFeed, CX Dive, Termly, US Chamber, Wiley | **Yes** — same utility class; CX Dive also in historical cascade `top_sources` |

Tavily latencies (prod key): ~1.8–2.0s. Serper playground (`google.serper.dev/w/search`): ~1–1.3s observed.

Raw Tavily half: `docs/delivery/_sta341-tavily-half.json`

### 2D. Recommendation

**Quality holds on the real sample → propose adopt Serper as primary; keep Tavily as optional fallback.**

| Decision | Detail |
| -- | -- |
| Provider | **Replace** Tavily as default (`WEB_RESEARCH_PROVIDER=serper` when wired); keep Tavily behind `WEB_RESEARCH_FALLBACK_TAVILY` |
| Metering | `metadata.provider=serper` on `usage_records` / research lookup metering |
| Pricing model | **Unchanged** — allotments 10/60/200, overage **$0.35**, stay metered/visible |
| Why not “keep Tavily only” | Real official Serper COGS is materially lower and quality matched on every historical distinct query available |
| Caveats | (1) n=2 — re-spot-check when real customer query volume grows; (2) need Serper API key on Railway; (3) training/retention ToS vs prior Google-governance choice is a separate owner review before customer-data-sensitive enablement |

**Integration plan (not implemented in this pass):**

1. Add `SERPER_API_KEY` + `web_research_provider=serper` settings.  
2. Implement `_search_serper` in `web_research.py` (POST `https://google.serper.dev/search`, map `organic[]` → title/url/snippet).  
3. Default prod to `serper` after live smoke meters `provider=serper`.  
4. Keep Tavily fallback for empty/error.  
5. Do **not** change billing allotments/overage/hide decision.

---

## Combined verdict

| Step | Verdict |
| -- | -- |
| 1 | **PASS** — prod is direct `tavily` |
| 2 | **Quality holds → recommend Serper primary + Tavily fallback**; pricing model unchanged |
