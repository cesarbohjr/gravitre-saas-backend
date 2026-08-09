# Adaptive Retrieval Layer — Program closure

**Status:** Closed (2026-07-18)  
**Prod tip at Milestone 1 sign-off:** `9d1ae051` (Research Manager merged @ `4eb6adbe`, PR #165)

This document is the program canvas for the adaptive retrieval layer work (Understand → Retrieve → Execute only). It records what shipped, what was live-verified, and what was explicitly closed as an accepted gap—not an open loop.

---

## Milestone 1 — Research Manager + stop-early cascade

**Status: PASS — shipped and live-verified**

Scope delivered:

- Research Manager with confidence-gated stop-early cascade in `UnifiedRetrievalService.retrieve()`
- Adaptive research prompt, pack source preferences, cascade SSE progress, research→action bridge (phases 1–6 on prod before RM merge)

Live evidence:

- Artifact: `docs/delivery/milestone1-live-reverify-latest.json`
- CI: [run 29632954299](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/29632954299) @ prod `9d1ae051`
- Canonical checks green: React write gate (Apollo deep-link), canvas write-authority, Wave 6–7, routing A–D, retrieval A/B 5/5

Tooling: `scripts/smoke-milestone1-live-reverify.py`, `scripts/smoke-retrieval-ab-live.py`, `.github/workflows/milestone1-live-reverify.yml`

---

## Milestone 2 (Performance Audit)

**Status: INCONCLUSIVE — closed by decision, not pursued further**

Closed **2026-07-18** by explicit program decision. The latency before/after guardrail was never measured with a real pre/post comparison on prod, and **will not be run** as part of this program. This is recorded plainly—not upgraded to PASS, not left as a dangling audit thread.

### Guardrails with live evidence

| Dimension | Result | Evidence |
|-----------|--------|----------|
| Internet search on internal-only probes | **PASS** | `internet_ran: false` on all internal probes; `INTERNET_RESEARCH_ENABLED` stays off |
| No write-tool leakage on read-only probes | **PASS** | `no_write_tools: true` on all five internal queries |
| HTTP availability on probes | **PASS** | All queries HTTP 200 @ prod `9d1ae051` |

Artifact: `docs/delivery/milestone2-performance-audit-latest.json`  
Closure record: `docs/delivery/milestone2-performance-audit-closure.json`

### Not measured (accepted gap)

| Dimension | Result | Notes |
|-----------|--------|-------|
| **Latency before/after delta** | **NOT MEASURED** | Binding guardrail was delta on same 5 internal queries pre- vs post–Research Manager. Tooling exists and is correct (`scripts/smoke-milestone2-latency-ab.py`, `scripts/railway_prod_deploy.py`, `.github/workflows/milestone2-latency-ab.yml`, corrected `scripts/smoke-milestone2-performance-audit.py`) but live A/B was not executed (blocked on prod rollback credentials; decision not to pursue). |
| **Token / cache delta** | **NOT MEASURED** | Same root cause; `task_type` filter in audit script was corrected for future use. |

### Context only — not a performance verdict

Post-merge probe latencies on prod @ `9d1ae051` (single run, no pre-RM baseline):

- p50 ≈ 22 s, p95 ≈ 25.9 s

These numbers are **context only**. They do **not** satisfy Milestone 2’s before/after guardrail and must **never** be cited as a performance PASS or FAIL for the Research Manager.

### If a production performance complaint surfaces later

This accepted gap is the first place to look. Tooling to answer the question already exists:

```bash
# When credentials available (backend/.env.operator.local or GitHub RAILWAY_TOKEN secret):
python3 scripts/smoke-milestone2-latency-ab.py --full-ab \
  --json docs/delivery/milestone2-latency-ab-latest.json
python3 scripts/smoke-milestone2-performance-audit.py \
  --latency-baseline docs/delivery/milestone2-latency-pre-rm-probe.json
```

Pre-RM SHA for comparison: `09e57595` (parent of `4eb6adbe`).

---

## Internet research governance

**Status: CLOSED (governance track)** — **`INTERNET_RESEARCH_ENABLED` stays OFF**; enablement not authorized

`INTERNET_RESEARCH_ENABLED` remains **off**. Milestone 2 confirmed internal probes do not invoke internet research while the flag is off.

### Prior position (Tavily)

Standard Tavily API tier: governance insufficient (training/retention); Enterprise tier: stronger but **out of budget**. No enablement on default Tavily.

### Recommended path (2026-07-18, governance closed)

**Grounding with Google Search** (Grounded Generation API) — **Tavily-equivalent** live web search, **not** Agent Search data-store queries:

- **Not** Custom Search JSON API (closed to new customers; EOL 2027-01-01).
- **Not** Agent Search $1.50–$4/1k data-store SKUs — indexed corpus RAG, not live open web.
- **Yes** Grounded Generation — grounding on Google Search — standard paid GCP API.
- **Same GCP project** as GSC OAuth / Gravitre OAuth client (not just “same vendor”).
- **Governance win:** Training Restriction on standard paid GCP; **caveat preserved:** no-training ≠ zero-retention (~30-day debug retention; zero-retention via DPA add-on).
- **List pricing (verified 2026-07-18):** $0/1k for first **10k grounding counts/day/account**; **$35/1k** above that (+ Gemini tokens). Source: [Google pricing — Example #2](https://cloud.google.com/generative-ai-app-builder/pricing).
- **Volume cost model at Gravitre scale:** **NOT RUN** — owner go/no-go still required before enablement.

**Current code:** Tavily-only (`backend/app/services/web_research.py`). No integration change until all enablement gates below are satisfied.

### Enablement go/no-go — three separate gates

Governance (“safe to use”) and economics (“safe to offer”) are **different** decisions. **`INTERNET_RESEARCH_ENABLED` must not go on for real customers until all three are satisfied:**

| # | Gate | Status | Notes |
|---|------|--------|-------|
| 1 | **Governance sign-off** | **CLOSED** | Grounding with Google Search recommended; no-training ≠ zero-retention caveat preserved. This close ≠ authorization to flip the flag. |
| 2 | **Volume estimate for cost forecasting** | **NOT RUN** | Owner must forecast daily grounding counts + token spend before go/no-go. |
| 3 | **Metering / credit pass-through with margin** | **NOT BUILT — named precondition** | Grounding + token costs scale with customer usage; must not be absorbed on Gravitre’s books without a revenue lever. See below. |

**Sequencing (2026-07-18):** Gate 3 is a **real, named blocker** on the canvas but **not built now** — same discipline as not building capability before it is needed. Pick up metering work only when seriously considering flipping the flag (after gate 2).

#### Why metering is required (not optional)

Google bills Gravitre **~$35/1k grounding counts/day above 10k free tier per account**, plus **Gemini tokens** on top. If internet research becomes popular, Gravitre’s cloud bill scales linearly with customer demand. Without pass-through (with margin), that is unbounded demand-driven cost with no corresponding revenue — fine in a pilot, problematic at scale.

#### Existing usage-billing primitives (repo audit, 2026-07-18)

| Mechanism | Status | Covers internet research today? |
|-----------|--------|----------------------------------|
| **`usage_tracking`** (`ai_credits`, `workflow_runs`, `operator_usage`, `rag_usage`) | **Live** — `backend/app/billing/service.py`, migrations under `supabase/migrations/` | **No** — `web_research.py` records nothing; no metric for grounding surcharges |
| **`ai_credits` + Node/Control/Command plans** | **Live** — token-derived credits from `model_calls`; included quotas per plan; Stripe Billing Meter reporting via `backend/app/billing/stripe_metering.py` when metered price IDs configured | **Partial** — grounded-generation **Gemini tokens** might map to existing `ai_credits`; **Google Search grounding surcharge** ($35/1k above free tier) is a **separate cost line** not represented in token math |
| **`intelligence_usage_logs`** (Intelligence Pack per-request cost logging) | **Not built** — proposed in Phase 0 MSP docs; **absent from repo** (`docs/delivery/phase0-executive-sales-msp-intelligence-packs.md`) | N/A — pack-specific future table; would need **extension or parallel path** for non-pack actions like internet research |

**Conclusion:** Gravitre has a **general org-level metering spine** (`usage_tracking` → Stripe meter for `ai_credits`), but **nothing today meters or bills internet-research / grounding calls**. Enabling the flag for customers requires extending that spine — not just adding a Google provider.

#### Two decisions — do not collapse them

| Decision | Owner | Status |
|----------|-------|--------|
| **A. Engineering / metering primitive** | Engineering (when gate 3 opens) | **Recommendation recorded:** meter internally via **`ai_credits`** pool; customer-facing unit = **research lookups** (same family as outputs/Mesons on [pricing page](https://gravitre.app/pricing)) — not a separate currency |
| **B. Pricing model** | Product / owner | **PROPOSAL RECORDED** — tier allotments + overage line item; **no tier price increase at launch** (revisit after gate 2) |

Decision A (which primitive) and Decision B (how plans price it) are related but **not the same**. A flat “$35/month baked into each plan” is a **pricing-model** choice that could still be implemented via included credits — or wrongly implemented as a hard-coded dollar line disconnected from usage.

#### Pricing-model options (owner decision — not built)

**Weaker: flat per-plan surcharge (e.g. “$35/month included in tier price”)**

- Assumes uniform usage across customers on a tier — breaks when usage is skewed (internal-only shops vs MSP pack customers hammering CVE/advisory lookups).
- Light users subsidize heavy users; research/lookup features tend toward heavy skew.
- **Margin risk in the wrong direction:** Google’s $35/1k is overage-tier pricing; if Gravitre eats a flat monthly cost regardless of actual grounding volume, one heavy customer past Google’s free tier can cost more than the flat fee recovers, while low-use customers are pure margin — inverted vs how variable cloud costs should be priced.
- Architecturally mismatched: variable-cost feature priced as fixed fee.

**Better fit: usage-based via `ai_credits` (matches existing stack)**

- Variable Google cost → variable customer metering through a primitive that already exists: plan-tier included quotas, overage via same pool, Stripe Billing Meter when configured.
- Architecturally coherent: usage-based cost through usage-based billing.

**Middle path — recorded direction**

Tie research to **plan tier**, not signup. One **included allotment** per tier; overage via existing pay-as-you-go pattern. Internally debits **`ai_credits`**; customers see **research lookups** (not “AI credits”) — consistent with pricing page exposing outputs and Mesons, not backend credit math.

**Why not signup-triggered free credits:** Second allotment mechanism alongside plan tier — rejected.

#### Market benchmark (cost per 1k queries — comparable to Google $35/1k overage)

| Product | Structure | Effective $/1k queries |
|---------|-----------|------------------------|
| Perplexity Sonar (raw search) | $5/1k, no synthesis | ~$5 |
| Perplexity Sonar Pro Search (agentic) | per-request | ~$14–22 |
| Perplexity Pro ($20/mo) | bundled fair-use | effectively unlimited within cap |
| Perplexity Enterprise Pro ($40/seat/mo) | ~1,733 searches/mo bundled | ~$23 all-in |
| Perplexity Enterprise Max ($325/seat/mo) | ~17,320/mo bundled | ~$18.8 all-in |
| **Google Grounded Generation** (Gravitre path) | $0 to 10k/day/account; $35/1k above | **$0–35** depending on volume |

Market per-query economics sit roughly **$5–23/1k**; Google’s **$35/1k is the high end**, offset by **10k/day/account free tier**. Size allotments assuming most usage stays under Google’s free line — not that every query costs $35.

#### Gravitre scale vs Google free tier (reframes COGS)

**Verified list prices** @ [gravitre.app/pricing](https://gravitre.app/pricing) (fetched 2026-07-18): Node **$49**, Control **$129**, Command **$299**; output caps **10 / 40 / 120** per month. Pay-as-you-go precedent: Additional Outputs **$2–3**, Additional Mesons **$2–4**.

Google free tier: **10,000 grounding counts/day/account** before $35/1k surcharge. Even if every Command output triggered one grounded search at full utilization: **120/month ≈ 4/day** — **~3 orders of magnitude** under the free threshold.

**Implication:** At current plan structure, **Google grounding surcharge is likely $0** for the foreseeable future; real variable cost is **Gemini tokens per grounded call** (smaller; overlaps existing token economics). This is not primarily “cover a $35/1k line item” — it is **package near-zero-marginal-cost capability as valuable, not free**, with overage priced for the edge case where patterns shift.

**Backend reference (internal, not customer-facing):** see **COGS reconciliation** below — do not assume `$0.02/$0.015/$0.012` were derived from Google grounding math.

#### COGS reconciliation — internal ledger vs customer-facing proposal (2026-07-18)

**Question:** Were `$0.02 / $0.015 / $0.012` per `ai_credit` derived the same way as the `$0.25–0.50` research lookup proposal?

**Answer: No — different snapshots, different purpose. Not inconsistent, but must not be conflated.**

| Rate | Origin | COGS basis | Relation to Google $35/1k |
|------|--------|------------|---------------------------|
| **`ai_credit` $0.02 / $0.015 / $0.012** | `DEFAULT_PLANS` in `backend/app/billing/service.py` since **2026-04-23** (Phase 16 billing, commit `185bf488`) | **LLM token overage** — `TOKENS_PER_CREDIT = 1000` (~$20/$15/$12 per million tokens before model multipliers) | **None** — predates internet-research governance; never tied to grounding |
| **DB `billing_plans.overage_rates`** (prod seed) | Migrations / `supabase/seed.sql` — keys **`output` / `meson`** ($2.50→$1.50 outputs; $3→$2 Mesons) | **Customer-facing units** on [pricing page](https://gravitre.app/pricing) | **None** — `_normalize_plan_row` merges DB over template; DB `overage_rates` **replaces** template wholesale → **`ai_credit` keys may be inactive in prod** when DB is seeded |
| **Research lookup $0.25–0.50** (proposal) | This session — **Additional Research Lookups** line (outputs/Mesons family) | **Expected COGS at scale:** Gemini tokens + **$0 grounding surcharge** (10k/day free tier). **Overage pricing narrative:** worst-case **$35/1k** as conservative safety-valve margin, not assumed per-query cost | **Dual:** expected COGS ≠ overage margin basis |

**Conclusion:** Existing internal `ai_credit` rates do **not** embed the pre-correction `$35/1k-as-baseline` mistake — they were never about grounding. The `$0.25–0.50` lookup range was framed against **worst-case** grounding for the dormant overage line; at current scale the honest expected COGS is **token cost only**. **Gate 3** must define **lookup → internal `ai_credits` debit** in one pass so customer price, internal ledger, and corrected COGS align — not two separate snapshots.

**No change required now** to `$0.02/$0.015/$0.012` for LLM metering. Research conversion is **net-new at build time**.

Artifact: [`internet-research-pricing-proposal.json`](./internet-research-pricing-proposal.json) → `cogs_reconciliation`

#### Proposed tier structure (proposal recorded — gate 2 validates)

**Definition:** 1 **research lookup** ≈ 1 grounded query (token ratio refined when volume data exists). Included lookups are **plan-tier allotments**; overage uses **Additional Research Lookups** — third line in the outputs/Mesons family, **not** a new customer currency.

| Tier | List price | Included research lookups/month | Tier price change at launch | Reasoning |
|------|------------|--------------------------------|-----------------------------|-----------|
| **Node** | $49 | **10** | **None** | 1:1 with 10-output cap; discoverable “try it” tier |
| **Control** | $129 | **60** | **None** (optional +$10–15 if positioned as distinct value-add) | ~1.5× 40-output cap; real research without unbounded exposure |
| **Command** | $299 | **200** | **None** (optional +$20–30) | Well above 120-output cap; unconstrained research positioning; still far below Google paid tier |
| **Overage (any tier)** | — | — | **Additional Research Lookups: $0.25–0.50 each** | Outputs/Mesons family; **expected COGS near-zero** at current scale; **$35/1k used only as worst-case overage margin basis**, not assumed per-query cost |

*Supersedes earlier benchmark-only anchors (Node ~15–25, Control ~150–300, Command ~750–1500) — those were pre–pricing-page; current proposal aligns to **output caps** and **verified COGS math**.*

**Launch recommendation (recorded):** **Do not raise tier prices** for internet research at launch. Free-tier math means charging more would be **optics-only**, not cost recovery — undercuts “intelligence included” positioning (“Pay for outputs and team seats — not buzzword tiers”). **Bundle generous capped allotments**; keep **$0.25–0.50/lookup overage** as the real margin protection, priced and ready but likely dormant until gate 2 confirms patterns.

**Optional tier bumps (+$10–15 Control / +$20–30 Command):** **NOT DECIDED.** Recorded lean: **no** — launch at **$0 tier increase**; let overage line carry margin if ever needed. Requires explicit owner sign-off if positioning changes.

**Gate 2 timing:** Run volume estimate when **real usage exists to measure** — not guessed ahead of enablement.

**Revisit tier pricing only if** gate 2 shows meaningful volume past Google’s free tier — then cost-driven increases use **real data**, not illustrative placeholders.

#### Owner decisions still required (before metering is built)

1. ~~**Included allotment per tier**~~ — **proposal recorded** (10 / 60 / 200 lookups); gate 2 validates assumptions.
2. **Grounding → internal `ai_credits` debit rate** — conversion + margin; customer sees lookups, not credits.
3. ~~**Customer-facing unit**~~ — **proposal recorded:** **research lookups** + **Additional Research Lookups** overage line (pricing-page family).
4. **Boundary behavior** — included exhausted → overage lookup purchase / pay-as-you-go (align with “What happens after I hit my limit?” on pricing page).

**Metering build status:** **NOT STARTED** — proposal on canvas; gate 2 validates volume/COGS; gate 3 implements.

Full analysis: [`internet-research-governance-google-vertex.md`](./internet-research-governance-google-vertex.md)  
Pricing proposal: [`internet-research-pricing-proposal.json`](./internet-research-pricing-proposal.json)  
Artifacts: [`internet-research-governance-latest.json`](./internet-research-governance-latest.json), [`internet-research-governance-closure.json`](./internet-research-governance-closure.json)

---

## Unaffected / already closed (this program)

The following remain closed and are **not** reopened by Milestone 2’s INCONCLUSIVE closure:

- OIL / claim investigations and related prod smokes
- Canvas write-authority, Wave 6–7 routing
- `should_plan` dead-end fix and related delivery artifacts
- Milestone 1 retrieval behavior (stop-early cascade, adaptive prompt, pack preferences)

Nothing is broken. One specific performance question (RM latency delta on internal-only queries) has no live-measured answer; that is now a **named, accepted gap**, not a hidden one.

---

## Program summary

| Item | Status |
|------|--------|
| Milestone 1 — Research Manager + cascade | **PASS** (live-verified) |
| Milestone 2 — Performance audit | **INCONCLUSIVE, closed by decision** |
| Internet research enablement | **SHIPPED (code)** — flip `INTERNET_RESEARCH_ENABLED=true` + live smoke pending |
| Retrieval-layer program | **Closed** |
