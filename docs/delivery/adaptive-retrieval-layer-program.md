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

Full analysis: [`internet-research-governance-google-vertex.md`](./internet-research-governance-google-vertex.md)  
Artifacts: [`internet-research-governance-latest.json`](./internet-research-governance-latest.json), [`internet-research-governance-closure.json`](./internet-research-governance-closure.json)

**Current code:** Tavily-only (`backend/app/services/web_research.py`). No integration change until owner sign-off + volume estimate.

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
| Internet research enablement | **OFF** — Google Vertex/grounding recommended; pricing + sign-off pending |
| Retrieval-layer program | **Closed** |
