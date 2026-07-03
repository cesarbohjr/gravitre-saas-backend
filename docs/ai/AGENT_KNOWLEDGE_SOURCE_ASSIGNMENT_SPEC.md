# Agent Knowledge Source Assignment — Full Spec (binding)

Status: **Approved for implementation** (phases A–F, human sign-off 2026-07-03).  
Last updated: 2026-07-03.

This document expands the Phase 1 audit **Critical gaps** into a complete, testable specification. It is the canonical reference for backend, frontend, sync, retrieval, and trust-layer behavior.

Related code:
- `backend/app/services/agent_knowledge_assignment_service.py`
- `backend/app/services/agent_knowledge_provenance_service.py`
- `backend/app/services/agent_knowledge_sync_service.py`
- `backend/app/services/agent_capability_profile_service.py`
- `backend/app/routers/agent_knowledge_assignments.py`
- `supabase/migrations/20260703180000_agent_knowledge_assignments.sql`
- `supabase/migrations/20260703190000_agent_knowledge_v2.sql`

---

## Human decisions (locked)

| # | Decision | Outcome |
|---|----------|---------|
| 1 | Route naming | Keep `/knowledge-assignments`; add `/knowledge-sources` as read/write alias |
| 2 | RBAC | **Admin-only** for create/update/delete/sync; org members may read assignments, capabilities, lineage, test-retrieval |
| 3 | Workspace boundary | **Org-scoped v1**; `workspace_id` column reserved, not required |
| 4 | Scheduler | Stay on **asyncio in-process scheduler** (same pattern as org-level `knowledge_sync_service`); no Temporal requirement for v1 |
| 5 | Legacy migration | **Read-time merge**: DB rows win; fall back to `agents.config.reference_folders` / `knowledge_packs`; config fallback on insert when table missing |
| 6 | GA4 / Canva / Figma | **Tool-data sources** — metadata/metrics/assets references only, not full document RAG |

---

## Problem statement

Enterprise agents must answer and act using **explicitly assigned, approved knowledge** — not the entire org corpus. Operators need:

1. Per-agent source bindings (Drive folders, CRM views, packs, etc.)
2. Reference-first storage (summaries + embeddings + URLs, not raw customer payloads)
3. Provenance (“Why does this agent know this?”)
4. Executable sync rules (include/exclude, tags, freshness)
5. Honest chat when assigned sources are missing or stale
6. Capability profiles that aggregate read/write/learn permissions

---

## Architecture overview

```
AgentKnowledgeAssignmentService (CRUD + config merge + retrieval filters)
├── AgentKnowledgeSyncService (per-assignment sync + rule evaluation)
├── AgentKnowledgeProvenanceService (reference rows + lineage + explain)
└── AgentCapabilityProfileService (read/write/learn aggregate)

Runtime path (assistant chat)
IntelligenceOrchestrator
├── list_assignments(agent_id)
├── build_prompt_section(assignments)
├── assigned_knowledge_gap_message(query)
└── UnifiedRetrievalService.retrieve(knowledge_assignments=[...])
    └── filter_rag_sources → assignment-scoped chunks only
        └── SSE: assignedSourcesUsed, knowledgeGapMessage, missingAssignmentLabels
```

Org-level knowledge sync (`knowledge_sync_service`, Notion/Confluence/HubSpot/Zendesk) remains separate but **feeds RAG** that assignment filters consume.

---

## Critical gaps → full specification

### Gap 1 — 20+ source types

**Audit gap:** DB allowed free-text; only `folder`, `knowledge_pack`, `dataset` in code.

**Full spec — canonical `source_type` enum**

| Type | Category | Connector vendor | Storage mode |
|------|----------|------------------|--------------|
| `google_drive_folder` | document | `google_drive` | reference + RAG chunks |
| `google_drive_file` | document | `google_drive` | reference + RAG chunks |
| `sharepoint_site` | document | `microsoft365` | reference + RAG chunks |
| `sharepoint_drive` | document | `microsoft365` | reference + RAG chunks |
| `sharepoint_folder` | document | `microsoft365` | reference + RAG chunks |
| `slack_channel` | communication | `slack` | reference summaries only |
| `teams_channel` | communication | `microsoft365` | reference summaries only |
| `hubspot_object` | crm | `hubspot` | reference + scoped CRM metadata |
| `salesforce_object` | crm | `salesforce` | reference + scoped CRM metadata |
| `zendesk_view` | support | `zendesk` | reference + ticket metadata |
| `intercom_collection` | support | `intercom` | reference summaries |
| `confluence_space` | document | `confluence` | reference + RAG via org sync |
| `notion_page` | document | `notion` | reference + RAG via org sync |
| `canva_folder` | tool_data | `canva` | metadata/assets only |
| `figma_project` | tool_data | `figma` | metadata/assets only |
| `ga4_property` | tool_data | `google_analytics` | metrics metadata only |
| `knowledge_pack` | pack | — | pack reference + installed RAG |
| `manual_rule` | rule | — | policy text / operator-defined |
| `folder` (legacy) | alias | `google_drive` | maps to `google_drive_folder` |
| `dataset` (legacy) | alias | — | maps to `manual_rule` |

**Validation:** `validate_source_type()` rejects unknown types at API layer (422).

**Acceptance:** POST with invalid type fails; legacy aliases normalize on write.

**Status:** **Shipped** — `backend/app/services/knowledge_source_types.py`

---

### Gap 2 — Full assignment schema

**Audit gap:** ~12 columns; missing connector_id, scopes, policies, etc.

**Full spec — `agent_knowledge_assignments` row**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `id` | uuid | yes | Primary key |
| `org_id` | uuid | yes | Tenant boundary |
| `agent_id` | uuid | yes | Agent owner |
| `source_type` | text | yes | Canonical enum value |
| `source_id` | text | yes | External id or pack id |
| `label` | text | yes | Human label |
| `include_rules` | jsonb[] | no | Glob/substring include patterns |
| `exclude_rules` | jsonb[] | no | Glob/substring exclude patterns |
| `sync_schedule` | text | no | Legacy cron-ish hint |
| `sync_frequency` | text | yes | `manual` \| `hourly` \| `daily` \| `weekly` |
| `sync_enabled` | bool | yes | Per-assignment toggle |
| `connector_id` | uuid | no | FK → `connectors` |
| `workspace_id` | uuid | no | Reserved (nullable v1) |
| `external_source_url` | text | no | Deep link for provenance UI |
| `owning_department` | text | no | Department scope hint |
| `read_scope` | jsonb | yes | Default `["read"]` |
| `write_scope` | jsonb | yes | Default `[]` |
| `learn_scope` | jsonb | yes | Default `["read","summarize"]` |
| `tags_required` | jsonb | no | Candidate must have tag |
| `tags_excluded` | jsonb | no | Candidate blocked if tag present |
| `freshness_policy` | jsonb | no | e.g. `{ "max_age_days": 90, "approved_only": true, "private_excluded": true }` |
| `permission_policy` | jsonb | no | Connector permission envelope |
| `provenance_required` | bool | yes | Default true |
| `owner_user_id` | uuid | no | Assignment owner |
| `created_by` | uuid | no | Admin who created |
| `confidence_score` | numeric | yes | 0–1 assignment trust |
| `last_synced_at` | timestamptz | no | Last successful sync |
| `last_verified_at` | timestamptz | no | Last permission verify |
| `freshness_status` | text | yes | `unknown` \| `fresh` \| `stale` \| `expired` |
| `enabled` | bool | yes | Soft disable |
| `metadata` | jsonb | no | Extensibility |

**Unique constraint:** `(org_id, agent_id, source_type, source_id)`.

**API serialization:** camelCase JSON (`sourceType`, `includeRules`, …).

**Status:** **Shipped** — migration `20260703190000_agent_knowledge_v2.sql`, assignment service v2.

---

### Gap 3 — Reference-first memory (no raw docs)

**Audit gap:** RAG stored chunks/embeddings without assignment link; no enforced reference-only policy.

**Full spec**

1. **`agent_knowledge_references` table** — one row per synced external object:
   - Stores: `memory_summary` (max 8000 chars), `external_url`, `source_title`, scores, `provenance_chain`, `embedding_reference`
   - Never stores: full email bodies, CRM export dumps, binary file content
   - `reference_only` must be `true` (enforced on upsert)

2. **RAG chunks** remain in org RAG pipeline but are **scoped at retrieval time** by assignment filters (see Gap 7).

3. **Ingest policy:**
   - Sync runners call `AgentKnowledgeProvenanceService.upsert_reference()` only
   - Block payloads > summary limit; truncate with log at debug
   - Tool-data sources (GA4, Canva, Figma) store metadata lines only

4. **Promotion to `agent_memories`:** existing memory promotion path must copy provenance envelope including `assignment_id` when present.

**Acceptance:** No reference upsert without `memory_summary`; integration test asserts no raw binary fields in reference rows.

**Status:** **Shipped** (reference table + upsert); **Partial** — RAG ingestion still org-wide; assignment link in chunk metadata is best-effort via title/id matching until ingest tags `assignment_id` on chunks.

**Follow-up (v1.1):** Tag RAG chunks with `assignment_id` at sync time for exact filter match.

---

### Gap 4 — Provenance / lineage APIs

**Audit gap:** Memory had `provenance` JSON; no explain API.

**Full spec — endpoints**

| Method | Path | Auth | Response |
|--------|------|------|----------|
| GET | `/api/agents/{id}/knowledge-assignments/{assignmentId}/provenance` | member | Assignment + scoped references + provenance chain |
| GET | `/api/agents/{id}/memory-lineage` | member | `{ lineage: [...] }` merged references + promoted memories |
| GET | `/api/agents/{id}/memories/{memoryId}` (existing) | member | Memory row; provenance envelope when present |

**Provenance explain shape**

```json
{
  "assignmentId": "uuid",
  "found": true,
  "label": "Brand guidelines",
  "sourceType": "google_drive_folder",
  "freshnessStatus": "fresh",
  "lastSyncedAt": "2026-07-03T12:00:00Z",
  "referenceOnly": true,
  "references": [
    {
      "id": "uuid",
      "title": "Brand guidelines",
      "sourceSystem": "google_drive",
      "externalUrl": "https://...",
      "freshnessScore": 0.85,
      "summary": "Reference to Google Drive folder..."
    }
  ],
  "provenanceChain": [{ "step": "drive_folder_assignment", "folder_id": "..." }]
}
```

**Memory explain (service method):** `explain_memory(org_id, agent_id, memory_id)` — same envelope fields from `agent_memories.provenance`.

**Acceptance:** Explain returns `referenceOnly: true` for all assignment-backed rows.

**Status:** **Shipped** — provenance service + router routes.

**Follow-up (v1.1):** Dedicated UI tab “Why does this agent know this?” on `/agents/[id]/knowledge` (lineage list exists in API; UI shows assignments panel only today).

---

### Gap 5 — Per-assignment sync rules + scheduler

**Audit gap:** Columns existed but rules not executed; freshness approximate only.

**Full spec — rule evaluation (`AgentKnowledgeSyncService.evaluate_rules`)**

Applied to each candidate object `{ name, title, tags, modified_at, approved, is_private }`:

1. **Exclude rules** — if pattern matches name/title → reject
2. **Excluded tags** — intersection with candidate tags → reject
3. **Required tags** — if set, candidate must intersect → else reject
4. **Include rules** — if any include rule set, at least one must match → else reject
5. **Freshness policy:**
   - `max_age_days` — reject if `modified_at` older
   - `approved_only` — reject if not approved
   - `private_excluded` — reject if private

**Sync runners (priority)**

| Source type | Runner behavior |
|-------------|-----------------|
| `knowledge_pack` | Register pack reference |
| `google_drive_*` | Folder/file reference + rule check |
| `hubspot_object`, `salesforce_object`, `zendesk_view`, `notion_page`, `confluence_space` | Connector reference via org connector |
| Other | Reference stub (`degraded: true`) until connector runner lands |

**Manual sync:** `POST /api/agents/{id}/knowledge-assignments/{assignmentId}/sync` (admin).

**Scheduled sync:** `assignment_is_due(assignment)` uses `sync_frequency` + `last_synced_at`.

**Freshness computation:** 72h fresh → stale → expired (assignment service `_compute_freshness`).

**On sync completion:** update `last_synced_at`, `last_verified_at`, `freshness_status`, `confidence_score`.

**On permission loss / delete:** `mark_stale_for_assignment(assignment_id, reason)`.

**Acceptance:** Unit tests for include/exclude/tags; sync updates assignment row timestamps.

**Status:** **Shipped** (service + manual sync API + rule tests).

**Follow-up (v1.1):** Wire `assignment_is_due()` into `knowledge/sync_scheduler.py` loop (org scheduler today does not call per-assignment sync).

---

### Gap 6 — Agent capability profiles

**Audit gap:** Only `agents.capabilities[]` array.

**Full spec — `GET /api/agents/{id}/capabilities`**

Aggregates:

| Field | Source |
|-------|--------|
| `connectedKnowledgeSources` | Enabled assignments |
| `allowedConnectors` | `agent_tool_permissions` |
| `availableReadActions` | Tool read scopes + assignment read scopes |
| `availableWriteActions` | Tool write scopes |
| `approvalRequiredActions` | Write actions flagged approval-required |
| `advisoryOnlyRestrictions` | Static policy strings |
| `learningSources` | Assignment labels/types enabled for learn |
| `memoryCount` | Count from `agent_memories` |
| `freshnessStatus` | Aggregate worst-of assignments |
| `lastSync` | Max `lastSyncedAt` |
| `confidenceScore` | Mean assignment confidence |
| `canRecommend` / `canExecuteWithApproval` | Derived booleans |

**Acceptance:** Profile returns non-empty read actions when assignments + tool perms exist.

**Status:** **Shipped** — `AgentCapabilityProfileService`.

**Follow-up (v1.1):** Frontend capabilities tab; plan/tier gates in `planRestrictions`.

---

### Gap 7 — Chat uses assigned sources only

**Audit gap:** Assignments in prompt text only; retrieval unfiltered.

**Full spec — retrieval scoping**

1. Orchestrator passes `knowledge_assignments` in retrieval parameters.
2. `UnifiedRetrievalService` after hybrid RAG:
   - Calls `filter_rag_sources(rag_sources, assignments)`
   - Match order: chunk metadata `assignment_id` → label in title → `document_id` in `sourceId`
3. Rebuilds `rag_section` from filtered sources only.
4. Metrics: `assignment_scoped`, `assignment_match_count`, `missing_assignments`.

**Chat honesty**

| Condition | Behavior |
|-----------|----------|
| No enabled assignments + query mentions brand/drive/guideline/etc. | Inject `knowledge_gap_message` into context; SSE `knowledgeGapMessage` |
| Assignments exist but zero RAG matches | Gap message: sync or adjust include rules |
| Matches found | SSE `assignedSourcesUsed` with title/score/documentId |

**Prompt sections:** `<knowledge_assignments>` + optional `<knowledge_gap>` in context profile.

**Escalation (future):** Org-wide retrieval only when explicit admin flag or `require_assigned_only: false` override — **not enabled in v1**.

**Acceptance:** Tests prove unassigned chunks dropped; gap message emitted for brand queries without assignments.

**Status:** **Shipped** — orchestrator + unified retrieval + SSE fields.

**Follow-up (v1.1):** Frontend `/ai` panel for `assignedSourcesUsed` and `knowledgeGapMessage` (SSE emitted; web not wired).

---

### Gap 8 — Demo workflows (4 flows)

**Audit gap:** No end-to-end templates with approval gates.

**Full spec — demo templates**

| ID | Name | Department | Approval | Required connectors |
|----|------|------------|----------|---------------------|
| `demo-launch-campaign` | Launch a Campaign | marketing | yes | google_drive, slack |
| `demo-stale-deals` | Find Stale Deals | sales | no | hubspot |
| `demo-customer-risk` | Summarize Customer Risk | customer_success | yes | zendesk, hubspot |
| `demo-support-triage` | Support Triage Report | support | no | zendesk |

Each template includes: `knowledgeAssignments`, `steps`, `sampleOutput`, `businessValue`, `requiredConnectors`, `optionalConnectors`.

**API:** `GET /api/agents/demo-knowledge-workflows` → `{ workflows: [...] }`.

**Acceptance:** Templates load; approval-gated demos have `requiresApproval: true`.

**Status:** **Shipped** — `backend/app/marketplace/demo_workflow_templates.py`.

**Follow-up (v1.1):** Marketplace install path that creates assignments + workflow from template; approval gate enforcement in workflow engine for demo ids.

---

### Gap 9 — API surface

**Audit gap:** Missing capabilities, provenance, lineage, test-retrieval, per-source sync.

**Full spec — route catalog**

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/agents/demo-knowledge-workflows` | member | List demo templates |
| GET | `/api/agents/{id}/knowledge-assignments` | member | List assignments |
| GET | `/api/agents/{id}/knowledge-sources` | member | Alias of list |
| POST | `/api/agents/{id}/knowledge-assignments` | admin | Create |
| POST | `/api/agents/{id}/knowledge-sources` | admin | Create alias |
| PATCH | `/api/agents/{id}/knowledge-assignments/{assignmentId}` | admin | Update |
| DELETE | `/api/agents/{id}/knowledge-assignments/{assignmentId}` | admin | Delete |
| POST | `/api/agents/{id}/knowledge-assignments/{assignmentId}/sync` | admin | Sync now |
| GET | `/api/agents/{id}/capabilities` | member | Capability profile |
| GET | `/api/agents/{id}/knowledge-assignments/{assignmentId}/provenance` | member | Explain assignment |
| GET | `/api/agents/{id}/memory-lineage` | member | Lineage list |
| POST | `/api/agents/{id}/knowledge-assignments/test-retrieval` | member | `{ query }` → scoped matches |

**Next.js proxies:** `apps/web/app/api/agents/[id]/knowledge-assignments/**`, `capabilities`, `test-retrieval`.

**Status:** **Shipped**.

---

### Gap 10 — Tests

**Audit gap:** 2 service tests only.

**Full spec — test matrix**

| Area | Test file | Cases |
|------|-----------|-------|
| Config merge | `test_agent_knowledge_assignment_service.py` | resolve_assignments, prompt section |
| Source types | `test_agent_knowledge_v2.py` | validate types, filter RAG, gap message, sync rules, demos |
| Orchestrator | `test_intelligence_orchestrator.py` | prepare turn with assignments path |
| Router CRUD + RBAC | `test_agent_knowledge_routes.py` (follow-up) | admin 403, tenant isolation |
| Sync integration | `test_agent_knowledge_sync.py` (follow-up) | Drive/HubSpot reference upsert |
| Chat honesty E2E | `test_assigned_knowledge_chat.py` (follow-up) | SSE gap fields |
| No raw storage | `test_reference_only_policy.py` (follow-up) | upsert rejects empty summary |

**Status:** **Partial** — core unit tests shipped; router/integration follow-ups listed.

---

## Trust layer (SSE contract)

Emitted on assistant `data-intelligence` chunk:

```json
{
  "knowledgeAssignments": [{ "label": "...", "sourceType": "...", "freshnessStatus": "..." }],
  "assignedSourcesUsed": [{ "title": "...", "score": 0.91, "documentId": "..." }],
  "knowledgeGapMessage": "I do not have an approved knowledge source assigned yet...",
  "missingAssignmentLabels": ["Brand guidelines"]
}
```

Frontend **should** surface gap messages inline and list assigned sources in trust/explainability panel.

---

## Frontend UX spec

| Surface | Requirement | Status |
|---------|-------------|--------|
| `/agents/[id]/knowledge` → **Assigned Sources** tab | List assignments, freshness, sync, test retrieval | **Shipped** |
| Capabilities summary cards | memory count, freshness, source count | **Shipped** (inline in tab) |
| Dedicated Capabilities route | Full profile + approval actions | Follow-up |
| Provenance / lineage UI | “Why does this agent know this?” | Follow-up |
| Source picker + rule builder | Create assignment from connector browser | Follow-up |
| Legacy Reference Folders tab | Keep until DB migration complete | **Shipped** (parallel) |
| `/ai` trust panel | Show `assignedSourcesUsed`, gap message | Follow-up |

**API client:** `agentKnowledgeApi` in `apps/web/lib/api.ts`.

---

## Security and tenancy

1. All queries scoped by `org_id` from auth context.
2. RLS on `agent_knowledge_assignments` and `agent_knowledge_references` — org member policy.
3. Writes require org admin (`require_admin`).
4. Sync uses org connector credentials; must not elevate agent beyond connector permission scope.
5. Reference rows never cross agent boundary without explicit assignment.
6. Test-retrieval is read-only but must not leak other agents’ sources (agent_id in path enforced).

---

## Legacy compatibility

| Legacy | Behavior |
|--------|----------|
| `agents.config.reference_folders` | Merged on read when no DB rows; flagged `fromConfig: true` |
| `agents.config.knowledge_packs` | Same |
| Insert when table missing | Falls back to config mutation (`_create_config_assignment`) |
| `folder` source type | Normalized to `google_drive_folder` |

**One-time migration script (optional follow-up):** Copy config folders/packs → DB rows for all agents.

---

## Acceptance criteria (release checklist)

| Criterion | Spec section | Required for v1 |
|-----------|--------------|-----------------|
| Assign specific knowledge sources | Gap 2, 9 | yes |
| 20+ validated source types | Gap 1 | yes |
| No raw document storage in references | Gap 3 | yes |
| Provenance / freshness / permissions fields | Gap 2, 4 | yes |
| Sync include/exclude rules executable | Gap 5 | yes (manual sync) |
| Capability profiles API | Gap 6 | yes |
| Chat retrieval scoped to assignments | Gap 7 | yes |
| Honest gap messaging | Gap 7 | yes |
| Demo workflow templates | Gap 8 | yes |
| Unit tests for core paths | Gap 10 | yes |
| Per-assignment scheduled sync | Gap 5 follow-up | no (v1.1) |
| Full frontend provenance UX | Gap 4 follow-up | no (v1.1) |
| RAG chunk `assignment_id` tagging | Gap 3 follow-up | no (v1.1) |

---

## Implementation status summary

| Phase | Scope | Status |
|-------|-------|--------|
| A | Schema + API + RBAC | **Shipped** |
| B | Reference-first + provenance | **Shipped** (chunk tagging partial) |
| C | Sync rules + runners | **Shipped** (scheduler hook partial) |
| D | Retrieval + chat honesty + SSE | **Shipped** (AI UI partial) |
| E | Capability profile + frontend tab | **Shipped** (full UX partial) |
| F | Demo templates + tests | **Shipped** (marketplace install partial) |

---

## v1.1 backlog (ordered)

1. Hook per-assignment due sync into `knowledge/sync_scheduler.py`
2. Tag RAG chunks with `assignment_id` during sync for exact retrieval match
3. Frontend: capabilities tab, provenance/lineage viewer, `/ai` trust fields
4. Router tests: RBAC + tenant isolation
5. One-time migration: `reference_folders` → DB assignments
6. Marketplace: install demo workflow → creates assignments + workflow graph
7. SharePoint / Slack / Salesforce full connector runners (beyond reference stub)
8. Memory promotion: require provenance envelope with `assignment_id`

---

## File index

| Component | Path |
|-----------|------|
| Assignment service | `backend/app/services/agent_knowledge_assignment_service.py` |
| Source types | `backend/app/services/knowledge_source_types.py` |
| Sync service | `backend/app/services/agent_knowledge_sync_service.py` |
| Provenance service | `backend/app/services/agent_knowledge_provenance_service.py` |
| Capability profile | `backend/app/services/agent_capability_profile_service.py` |
| Router | `backend/app/routers/agent_knowledge_assignments.py` |
| Retrieval filter | `backend/app/services/unified_retrieval_service.py` |
| Orchestrator wiring | `backend/app/services/intelligence_orchestrator.py` |
| SSE metadata | `backend/app/operators/assistant_sse.py` |
| Demo templates | `backend/app/marketplace/demo_workflow_templates.py` |
| Migration v1 | `supabase/migrations/20260703180000_agent_knowledge_assignments.sql` |
| Migration v2 | `supabase/migrations/20260703190000_agent_knowledge_v2.sql` |
| Frontend panel | `apps/web/components/agents/agent-knowledge-assignments-panel.tsx` |
| Tests | `backend/tests/services/test_agent_knowledge_v2.py` |
