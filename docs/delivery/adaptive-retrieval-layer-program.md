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
- **Volume cost model at Gravitree scale:** **NOT RUN** — owner go/no-go still required before enablement.

**Current code:** Tavily-only (`backend/app/services/web_research.py`). No integration change until all enablement gates below are satisfied.

### Enablement go/no-go — three separate gates

Governance (“safe to use”) and economics (“safe to offer”) are **different** decisions. **`INTERNET_RESEARCH_ENABLED` must not go on for real customers until all three are satisfied:**

| # | Gate | Status | Notes |
|---|------|--------|-------|
| 1 | **Governance sign-off** | **CLOSED** | Grounding with Google Search recommended; no-training ≠ zero-retention caveat preserved. This close ≠ authorization to flip the flag. |
| 2 | **Volume estimate for cost forecasting** | **NOT RUN** | Owner must forecast daily grounding counts + token spend before go/no-go. |
| 3 | **Metering / credit pass-through with margin** | **NOT BUILT — named precondition** | Grounding + token costs scale with customer usage; must not be absorbed on Gravitree’s books without a revenue lever. See below. |

**Sequencing (2026-07-18):** Gate 3 is a **real, named blocker** on the canvas but **not built now** — same discipline as not building capability before it is needed. Pick up metering work only when seriously considering flipping the flag (after gate 2).

#### Why metering is required (not optional)

Google bills Gravitree **~$35/1k grounding counts/day above 10k free tier per account**, plus **Gemini tokens** on top. If internet research becomes popular, Gravitree’s cloud bill scales linearly with customer demand. Without pass-through (with margin), that is unbounded demand-driven cost with no corresponding revenue — fine in a pilot, problematic at scale.

#### Existing usage-billing primitives (repo audit, 2026-07-18)

| Mechanism | Status | Covers internet research today? |
|-----------|--------|----------------------------------|
| **`usage_tracking`** (`ai_credits`, `workflow_runs`, `operator_usage`, `rag_usage`) | **Live** — `backend/app/billing/service.py`, migrations under `supabase/migrations/` | **No** — `web_research.py` records nothing; no metric for grounding surcharges |
| **`ai_credits` + Node/Control/Command plans** | **Live** — token-derived credits from `model_calls`; included quotas per plan; Stripe Billing Meter reporting via `backend/app/billing/stripe_metering.py` when metered price IDs configured | **Partial** — grounded-generation **Gemini tokens** might map to existing `ai_credits`; **Google Search grounding surcharge** ($35/1k above free tier) is a **separate cost line** not represented in token math |
| **`intelligence_usage_logs`** (Intelligence Pack per-request cost logging) | **Not built** — proposed in Phase 0 MSP docs; **absent from repo** (`docs/delivery/phase0-executive-sales-msp-intelligence-packs.md`) | N/A — pack-specific future table; would need **extension or parallel path** for non-pack actions like internet research |

**Conclusion:** Gravitree has a **general org-level metering spine** (`usage_tracking` → Stripe meter for `ai_credits`), but **nothing today meters or bills internet-research / grounding calls**. Enabling the flag for customers requires extending that spine — not just adding a Google provider.

#### Two decisions — do not collapse them

| Decision | Owner | Status |
|----------|-------|--------|
| **A. Engineering / metering primitive** | Engineering (when gate 3 opens) | **Recommendation recorded:** fold grounding into existing **`ai_credits`** — do not invent a third customer-facing unit |
| **B. Pricing model** | Product / owner | **NOT DECIDED** — how plan tiers cover research cost (flat inclusion vs usage-based vs hybrid) |

Decision A (which primitive) and Decision B (how plans price it) are related but **not the same**. A flat “$35/month baked into each plan” is a **pricing-model** choice that could still be implemented via included credits — or wrongly implemented as a hard-coded dollar line disconnected from usage.

#### Pricing-model options (owner decision — not built)

**Weaker: flat per-plan surcharge (e.g. “$35/month included in tier price”)**

- Assumes uniform usage across customers on a tier — breaks when usage is skewed (internal-only shops vs MSP pack customers hammering CVE/advisory lookups).
- Light users subsidize heavy users; research/lookup features tend toward heavy skew.
- **Margin risk in the wrong direction:** Google’s $35/1k is overage-tier pricing; if Gravitree eats a flat monthly cost regardless of actual grounding volume, one heavy customer past Google’s free tier can cost more than the flat fee recovers, while low-use customers are pure margin — inverted vs how variable cloud costs should be priced.
- Architecturally mismatched: variable-cost feature priced as fixed fee.

**Better fit: usage-based via `ai_credits` (matches existing stack)**

- Variable Google cost → variable customer metering through a primitive that already exists: plan-tier included quotas, overage via same pool, Stripe Billing Meter when configured.
- Architecturally coherent: usage-based cost through usage-based billing.

**Middle path (likely answer when gate 3 opens — recommendation only, not decided)**

Combines tier generosity with usage alignment without a third unit:

1. Each plan tier (Node / Control / Command) gets a **baseline included allotment** of research/grounding usage, expressed as **`ai_credits`** at a documented conversion rate **with margin** over Google’s $35/1k grounding cost (+ token costs). This is the “included research” idea done as **included credits**, consistent with how the rest of the platform meters — not a hard-coded dollar line item.
2. Usage **beyond** the included allotment draws from the customer’s **general `ai_credits` balance** (same pool as LLM usage), or triggers top-up / overage flow — consistent with whatever `ai_credits` already does at quota today.
3. Reuses existing Stripe metering; avoids overcharging light users and undercharging heavy ones; no third customer-facing unit.

**Optional product exception:** Keep research visible as its own **line item in UI/usage reports** for transparency while still debiting the **same underlying `ai_credits` currency** — distinct display, shared pool.

#### Owner decisions required (before metering is built)

1. **Included research allotment per tier** — e.g. Node none/limited, Control X, Command Y (in `ai_credits` terms).
2. **Conversion rate + margin** — grounding count (+ associated tokens) → `ai_credits`, with margin over Google’s verified $35/1k overage rate.
3. **Single pool vs separate balance** — default lean: **reuse existing `ai_credits` pool** unless product wants a separate research balance for transparency (same currency, optional separate reporting).
4. **Boundary behavior** — at included allotment / platform limits: stop, throttle, or charge from general balance with transparent notice (align with existing overage UX).

**Metering build status:** **NOT STARTED** — Gate 3 remains a documented precondition. When seriously considering enablement (after gate 2 volume estimate), the **likely** pricing answer is: **included `ai_credits` allotment per tier + margin + shared Stripe-metered pool** — not a flat $35/month line item. That is a **recommendation for when the gate opens**, not authorization to build now against an unverified volume estimate.

Full analysis: [`internet-research-governance-google-vertex.md`](./internet-research-governance-google-vertex.md)  
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
| Internet research enablement | **OFF** — governance **CLOSED**; volume estimate + metering **NOT RUN / NOT BUILT** |
| Retrieval-layer program | **Closed** |
