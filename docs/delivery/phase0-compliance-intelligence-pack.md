# Phase 0 — Compliance Intelligence Pack (#11)

**Date:** 2026-07-18  
**Mode:** Guidance / governance lock only — **no pack install, no connectors, no tip smoke**  
**Program row:** Pack #11 — Compliance  
**Owner (scope & PHI):** Cesar Bohorquez Jr. (STA-312 licensing / data-governance owner)

---

## Verdict (this pass)

| Layer | Status |
|-------|--------|
| Guidance docs (this file + program row) | **DONE** |
| Marketplace `intelligence_pack` install / demo agent | **NOT BUILT** — held |
| SOC2 / ISO / HIPAA / CMMC document connectors | **NOT BUILT** — held |
| Live EHR / clinical / member health data | **STOP** — PHI |
| Tip smoke / live invoke | **N/A** this pass |

Pack #11 closes the **12-pack guidance obligation** for Compliance. It does **not** authorize a customer-facing Compliance pack build until Cesar clears PHI-vs-guidance scope for any source that could carry protected health information.

---

## Goal (locked)

Help operators prepare **audit readiness** against **public framework guidance** (NIST-style control narratives, policy checklists, evidence *mapping* language) — not ingest patient, clinical, or other PHI systems.

**Job to be done (v1, when/if built):** “What controls and evidence stubs do we still need for SOC2 / ISO-style readiness?” using **customer-uploaded or Gravitre-authored guidance documents**, never live PHI stores.

---

## Identity (reserved — do not seed until build authorized)

| Field | Value |
|--------|--------|
| **pack_id / slug** | `compliance-intelligence-pack` *(reserved; not in `catalog.py` yet)* |
| **title** | Compliance Intelligence Pack |
| **department** | `compliance` (or `security` — product pick at build) |
| **default_subdomain** | `audit_readiness` |
| **tier** | `starter` |
| **tags** | `compliance`, `audit`, `guidance`, `intelligence-pack` |
| **Demo agent (vision)** | Compliance Agent — **NEW** (`phase0-twelve-pack-marketplace-vision.md`) |
| **External connectors (this pass)** | **None** |

Related existing catalog (not this pack): marketplace knowledge asset `compliance-operations-knowledge` (`seed_catalog_expansion.py`) — policy / evidence *RAG stubs* only.

---

## PHI stop-line (hard)

**Rule:** If a proposed source, connector, upload path, Memory write, or KG entity **could** contain **PHI** (or treat as PHI under customer contract / HIPAA), **stop**. Engineering must **not** decide edge cases.

| Allowed (guidance only) | Forbidden without Cesar named clear |
|-------------------------|-------------------------------------|
| Public NIST / CSF / SP 800-53 *control family summaries* authored or curated by Gravitre | EHR / EMR / FHIR clinical APIs |
| Customer-uploaded **policies**, **control matrices**, **SOC2 report PDFs** they already own (non-PHI) | Member/patient demographics, claims, clinical notes |
| Mapping language: “control → evidence artifact type” | Any connector labeled healthcare / payer / clearinghouse |
| Reuse of product `compliance_service` PII redaction / SOC2 *evidence export* (STA-81/82) as **platform** capability | Writing raw identity or health fields into Organizational Memory / KG |
| FedRAMP readiness notes in `docs/compliance/fedramp-gap-analysis.md` | Live “compliance vendor” scrape of customer health data |

**Same pattern as:** Crunchbase / GSC raw-query / Memory Option B — governance owner + written option before purpose expands.

**Ambiguity rule:** If unsure whether content is PHI → treat as **STOP** and escalate to Cesar. Do not “redact and proceed” as a substitute for sign-off.

---

## In scope vs out of scope

### In scope (docs / future guidance pack)

1. Framework **guidance** corpora (NIST-style), control checklists, audit-readiness narratives  
2. Optional future workflow: **Audit Readiness** (vision table — NEW orchestration only; no new PHI connectors)  
3. Pack KPI / notify / `result_url` cohesion **when** pack is built (reuse Phase 3.5 patterns)  
4. Explicit stop-lines in agent guardrails: `phi_sources_blocked`, `guidance_docs_only`, `no_ehr_connectors`

### Out of scope (this pass and until separate clear)

1. Any live SOC2 / ISO / HIPAA / CMMC **document vault** connector productization  
2. Healthcare / HRIS-adjacent clinical data (HR pack already holds employee PII separately)  
3. Claiming FedRAMP / HIPAA / SOC2 **authorization** via this pack  
4. Council / mock “compliance scoring” over real customer PHI  
5. Business OS (#12) rollup of compliance KPIs (last in sequence)

---

## Framework reuse (when build is authorized)

Mirror **Platform Health** (internal / no risky external PHI) more than Finance/HR:

| Primitive | Reuse |
|-----------|--------|
| Catalog → seed → demo install → PackKpiPanel | Same as CS / Platform Health |
| Shared ingestion → KG → PackSignal | Only for **non-PHI guidance** entities with provenance |
| Approval gate | Required for any write that mutates customer policy corpus |
| `emit_notification` / `result_url` | Tip read of control checklist or evidence map |
| `compliance_service.redact_*` / SOC2 export | Platform helpers — **not** pack connectors |

Do **not** copy Finance/HR OAuth stub patterns for EHR vendors.

---

## Proposed signals (future — not implemented)

| id | Detect | Severity | Gate |
|----|--------|----------|------|
| `compliance.control_gap_open` | Guidance checklist item unmarked | medium | docs only |
| `compliance.evidence_stub_missing` | Control mapped, no evidence artifact type | medium | docs only |
| `compliance.phi_source_blocked` | Install/tool attempted forbidden source | high | always |

No signal may fire from PHI payloads.

---

## Proposed KPIs (future — not implemented)

| KPI | Source |
|-----|--------|
| `guidanceDocsAssigned` | knowledge assignments |
| `openControlGaps` | checklist / signals |
| `phiStopLineHonored` | always true in tip; fail closed if violated |
| install / agent / workflow counts | shared `pack_kpi_summary` |

---

## Governance checklist (before any build PR)

- [ ] Cesar confirms pack build may proceed **guidance-docs-only** (named written clear)  
- [ ] No connector types for EHR/clinical/PHI vendors in template  
- [ ] Agent guardrails include `phi_sources_blocked` + `guidance_docs_only`  
- [ ] Memory/KG writers reject PHI-classified entity types (or pack has zero KG writes)  
- [ ] Tip smoke proves **no** live PHI invoke; optional guidance RAG tip only  
- [ ] Marketing copy does **not** claim HIPAA/FedRAMP ATO via pack install  

Until the first box is checked, engineering ships **docs only** (this file).

---

## Related artifacts

| Artifact | Role |
|----------|------|
| `docs/delivery/phase0-twelve-pack-marketplace-vision.md` | Vision: Compliance Agent NEW; docs vs PHI gate |
| `docs/delivery/master-knowledge-intelligence-packs-program.md` | Program row #11 |
| `docs/compliance/fedramp-gap-analysis.md` | Platform FedRAMP readiness (not pack) |
| `backend/app/services/compliance_service.py` | STA-81/82 redaction + SOC2 export helpers |
| Marketplace `compliance-operations-knowledge` | Existing knowledge_pack seed (RAG stubs) |

---

## Explicit non-claims

- This document is **not** a SOC2, ISO, HIPAA, CMMC, or FedRAMP authorization.  
- Installing a future Compliance pack does **not** make a tenant compliant.  
- Platform evidence export (STA-81) ≠ pack tip PASS for regulated data.

---

## Next

1. **Program:** mark Pack #11 guidance **DONE** (this pass).  
2. **Build:** wait for Cesar named clear → then catalog + install + tip (guidance RAG only).  
3. **Sequence:** Pack #12 Business OS rollup remains **last**.
