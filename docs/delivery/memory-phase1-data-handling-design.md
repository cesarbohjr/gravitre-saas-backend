# Memory Phase 1 — data-handling design (pre-code)

**Status:** Draft for governance review — **no Memory embedding code authorized**  
**Date:** 2026-07-12  
**Parent gate:** ADR 001 (`docs/decisions/001-defer-ml-disambiguation-until-schema-stable.md`)  
**Related (closed, engineering-only):** `docs/delivery/adr001-sensitive-schema-audit.json`  
**Authorization tracker:** `docs/delivery/adr001-memory-authorization-review.json`

## Purpose

Separate **schema-gate evidence** (WorkflowFieldSpec coverage) from **authorization to embed identity-style fields** for chat assignee/entity disambiguation. This document answers the data-handling questions that must be resolved before Memory Phase 1 embeddings may be built or signed off.

This is **not** an implementation plan. No embedding index, no new provider calls for Memory, until this design is approved and sign-off ownership (Q5) is clear.

---

## Category boundary (do not collapse)

| Claim | Status | Authorizes |
| --- | --- | --- |
| ADR 001 schema-gate (≥5 priority connectors with multi-field assignee/email-style `sensitive` WorkflowFieldSpecs) | **Met in code** — freeze as closed engineering evidence | Nothing about third-party embedding of customer PII |
| Memory Phase 1 embeddings for chat fill / entity disambiguation | **Paused** | Requires this design + explicit governance sign-off |

`WorkflowFieldSpec.sensitive=True` today means: **do not auto-infer** these args; any future ML resolver must attach to the schema. It is **not** permission to send those values to an embedding API.

---

## Proposed product scope (if ever approved)

**Goal:** Improve chat parameter fill for *sensitive* entity fields (assignee, email-style identity, Slack channel) when the user gives a fuzzy mention (“Sarah”, “the Acme contact”, “#sales”) — as a **pluggable resolver behind `WorkflowFieldSpec`**, with fallback to today’s rule-based path and low-confidence approval UX (ADR 001 consequences).

**Out of scope for Phase 1:** RAG KB upgrade, Recommendation ML, Forecasting/GNN/CV, bulk CRM export embedding, cross-org indexes.

**Corpus candidates (identity-adjacent only):**

| Source field class | Examples | Sensitivity |
| --- | --- | --- |
| Email-style identity | HubSpot/Apollo contact email | High — customer PII |
| Person assignee | Asana/Jira assignee display name / hint | High — personal data |
| Channel-as-entity | Slack channel name/id | Medium — workspace metadata; may still be customer-identifying |

---

## 1. WHAT gets embedded

### Recommendation (engineering default — prefer least-raw)

**Do not embed raw emails or raw assignee display names in Phase 1.**

| Layer | What is stored / sent | Rationale |
| --- | --- | --- |
| Durable identity (existing) | Keep using `org_entity_resolution_records`: normalized alias → `entity_id` (exact/normalized match) — **no vectors required for v1 utility** | Already ships; zero new third-party identity traffic |
| If embeddings are still required after product proof | Embed **opaque, org-scoped tokens only**, never raw PII: e.g. `mem:{org_id}:{entity_type}:{entity_id}` or a keyed HMAC of canonical id (`HMAC-SHA256(org_secret, entity_id)`) | Provider sees non-reversible tokens; similarity is over *mentions of known entities*, not over email strings |
| Query side | Embed the **user mention fragment** after the same normalization used for alias match (lower/trim); optionally redact email-shaped substrings before provider call | Aligns with `AI_PII_REDACTION_ENABLED` spirit |

**Raw embedding of email / assignee name / channel name is not proposed.** If a later revision claims raw is “genuinely required,” it must justify with measured recall lift vs token/HMAC approach and accept a higher governance bar (almost certainly legal/DPA).

**Phase 1 product alternative (preferred if disambiguation quality is already adequate):** ship **no new embeddings** — extend rule-based + `org_entity_resolution_records` only. That still honors ADR’s “attach to WorkflowFieldSpec” by reading `sensitive` / `inferrable` flags without a vector store.

---

## 2. WHICH provider

### Existing stack (RAG — different purpose)

- Default: OpenAI `text-embedding-3-small` (1536) → Postgres `rag_embeddings` / pgvector  
- Optional: Voyage `voyage-3` (see `docs/voyage-reindex-runbook.md`)  
- Documented in `docs/security/DATA_STORAGE_AND_LLM_TRANSMISSION.md` for **knowledge-base chunk** embeddings

### Memory Phase 1 — engineering recommendation

| Option | Proposal | DPA implication |
| --- | --- | --- |
| **A — No new provider call (preferred)** | No Memory embedding provider; exact/normalized resolution only | No new purpose; no new third-party identity traffic |
| **B — Reuse OpenAI embedding path with opaque tokens only** | Same `get_embedding` / model as RAG, **separate table/index**, inputs restricted to opaque tokens + redacted mention fragments | **Do not assume** the existing RAG/KB DPA covers this. RAG purpose = document chunks for retrieval. Memory purpose = **entity/assignee embedding for chat parameter fill**. Same vendor ≠ same purpose. **Requires explicit DPA/purpose confirmation** before Option B. |
| **C — Separate provider** | New vendor or dedicated Memory endpoint | New DPA/purpose review required; not preferred |

**Explicit denial of assumption:** Reusing OpenAI `text-embedding-3-small` for Memory does **not** inherit RAG/KB contractual coverage by engineering inference. Coverage for this **new purpose** is an open compliance question (see §5).

---

## 3. STORAGE and RETENTION

### Recommendation

| Mode | Proposal |
| --- | --- |
| **Phase 1 default** | **No persisted Memory vectors.** Prefer in-process / request-scoped embedding of query mention only (if Option B), or no embeddings (Option A). |
| If persistence is later approved | Dedicated table e.g. `org_memory_entity_embeddings` (org RLS), **not** mixed into `rag_embeddings`. Columns: `org_id`, `entity_type`, `entity_id`, `embedding`, `model_version`, `created_at`, `expires_at`. No raw email/name columns. |

### Retention / purge (must be true before persistence is allowed)

| Control | Requirement |
| --- | --- |
| Local purge | Hard-delete rows by `org_id` and by `expires_at`; wire to org offboarding and an admin “purge Memory embeddings” action |
| Retention default | Short — propose **30 days** max for persisted Memory vectors (tighter than RAG corpus), or TTL tied to `memory_retention_days` if product prefers one knob |
| Provider-side | **Cannot claim** ability to delete OpenAI/Voyage provider logs or training-exclusion beyond what the vendor contract already states. Design must **disclose this gap** (already flagged for chat/RAG diligence in `DATA_STORAGE_AND_LLM_TRANSMISSION.md`). Prefer Option A or ephemeral query embeddings to minimize exposure. |
| Redis | Do not cache Memory identity embeddings with raw mention text longer than existing query-embedding TTL without redaction; treat as sensitive ephemeral storage |

---

## 4. ORG-LEVEL CONTROL

### Recommendation

| Control | Proposal |
| --- | --- |
| Default | **Off (opt-in)** for any Memory embedding path that calls a third party — including opaque-token Option B |
| Minimum | Org setting e.g. `settings.memoryEntityEmbeddings.enabled` (bool, default `false`) |
| Prefer | Opt-in plus optional per-connector allowlist (`hubspot` / `apollo` / `jira` / `asana` / `slack`) |
| Kill switches | Honor `DISABLE_AI`; respect `organizations.data_region`; reuse `modelPolicy` blocks if embedding provider is denied for the org |
| UX | Settings copy must state purpose: “Improve chat matching of people/channels” and that a third-party embedding API may receive **non-raw tokens / redacted mentions** (never claim “no data leaves Gravitre” if a provider is used) |

Exact/normalized `org_entity_resolution_records` (no embeddings) may remain available under existing connector/chat behavior unless product decides that store also needs a separate toggle — **flag for product**; default leave as-is since it already exists without a new provider purpose.

---

## 5. WHO OWNS SIGN-OFF

| Reviewer | Role in this decision |
| --- | --- |
| Engineering | Schema-gate evidence; technical feasibility of Option A/B; purge implementability for **local** stores |
| Product / operator owner (this thread) | Whether Memory embeddings are needed at all vs extending rule-based resolution; opt-in defaults |
| **Compliance / legal / DPA owner** | Whether Option B (or any third-party embedding of identity-adjacent traffic) is covered under existing agreements for this **new purpose**; residency implications |

### Gap to flag

This repository and prior delivery artifacts do **not** name a standing compliance/legal approver for new AI data purposes. If no such role exists in the org, **that is itself a blocker** for Option B/C — not something engineering can self-certify.

**Until Q5 is answered with a named reviewer (or an explicit written decision that the operator owner accepts governance risk with no separate legal function), Memory Phase 1 embeddings stay paused** even if Options A–D below are product-preferred.

---

## Decision options (for governance)

| Option | Summary | Embedding code? | Third-party identity traffic? |
| --- | --- | --- | --- |
| **A** | Extend rule-based + `org_entity_resolution_records` only; attach to `WorkflowFieldSpec.sensitive` for “never invent” | No | No new |
| **B** | Opt-in Memory vectors of **opaque entity tokens** + redacted mention queries; separate table; reuse OpenAI embed API **only after DPA purpose confirmation** | Yes, after sign-off | Yes (tokens/redacted fragments) |
| **C** | Separate embedding provider | Yes, after sign-off + new DPA | Yes |
| **D** | Raw PII embedding | **Rejected** in this draft | — |

**Engineering recommendation:** choose **A** unless product can show a measured failure of exact/normalized resolution that only embeddings fix. If embeddings are required, choose **B** only after Q5 + DPA purpose confirmation — never raw.

---

## Explicit non-goals until approval

- No Memory embedding index / vector search implementation  
- No mixing identity vectors into `rag_embeddings`  
- No treating ADR schema-gate `met: true` as Memory authorization  
- No change to STA-305 / STA-309 / STA-310 / STA-311 closures

---

## Review checklist (before any Memory embedding PR)

- [ ] Option A / B / C selected in writing  
- [ ] If B or C: DPA/purpose coverage confirmed (not inferred from RAG)  
- [ ] Storage mode + retention + local purge specified; provider-log gap disclosed  
- [ ] Org default = opt-in (or documented exception)  
- [ ] Named sign-off owner for data governance (Q5) recorded  
- [ ] Authorization tracker updated only after the above
