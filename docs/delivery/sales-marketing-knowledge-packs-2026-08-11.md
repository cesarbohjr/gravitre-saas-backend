# Sales & Marketing Knowledge Packs — open/gov path (2026-08-11)

## Verdict

Extended existing A–E Source Registry (no parallel license scheme). Live license re-verification **halted OpenStax** shared-corpus ingest (CC BY-NC-SA, not CC BY). Ingested FTC / SBA / Census structured catalog + **provenance-filtered** Saylor syllabi. HubSpot + Google Trends = type D live-only.

## Phase 0 — Classification reconciliation

| Proposed `ingestion_policy` | Mapped onto existing A–E |
| -- | -- |
| FULL | A/B + `commercial_use_allowed=true` + bulk/api |
| FILTERED | A + `third_party_content_present` + provenance filter |
| API | B + `ingestion_method=api` |
| REFRESHABLE | A/B + weekly/daily refresh |
| LIVE_RETRIEVAL | **D** + `live_only` |
| METADATA_ONLY | hold / no chunks |
| BLOCKED_LICENSE | `commercial_use_allowed=false` + `blocked_nc` |

New columns on `knowledge_sources` (migration `20260811210000_knowledge_sources_license_metadata.sql`):
`license`, `license_url`, `derivatives_allowed`, `third_party_content_present`, `legal_review_status`.

Hard gate: `assert_ingest_allowed(..., commercial_use_allowed=True)` — false/None refused. DB CHECK mirrors for active A/B rows.

## Live license re-verification

| Source | Prompt claim | Live finding | Action |
| -- | -- | -- | -- |
| OpenStax Principles of Marketing | CC BY 4.0 → ingest A | **CC BY-NC-SA 4.0** on preface + ch.1 | **HALT** — `blocked_nc`, type C hold |
| Saylor courses | CC BY 3.0 Saylor-authored; 3P varies | Footer confirms CC BY 3.0 + third-party various | FILTERED syllabi only |
| FTC | Gov / public domain | Website policy: public domain (17 U.S.C. § 105) | Ingest A, refreshable |
| SBA | Gov | Privacy notice: gov info public domain; 3P may be copyrighted | Ingest A (SBA pages) |
| Census | API | ToS: API use OK + attribution notice; API key | Type B structured |
| Google Trends | API alpha / fallback | No official API key configured; explore URL live | Type D live-only |
| HubSpot | Do not permanent ingest | Type D live_retrieval_only | No corpus write |

Evidence JSON: `docs/delivery/sales-marketing-license-verify-live.json`.

## Decision (2026-08-11) — keep blocked

Cesar: keep **OpenStax** and **Saylor unit-reading / authenticated provenance** blocked until further clarification.

| Path | Status |
| -- | -- |
| OpenStax Principles of Marketing | Stay `blocked_nc` / paused — no corpus ingest |
| Saylor unit readings | Stay excluded — syllabi/intros only; no enrollment deep-dive |
| FTC / SBA / Census / Saylor syllabi | Unchanged (already live) |

Reopen only with explicit human choice after OpenStax commercial clarification and/or a paid-methodology priority call.

## Phase 1 — OpenStax

**HALTED / blocked until further clarification.** Registry: `marketing.openstax.principles`, `legal_review_status=blocked_nc`.

## Phase 2 — Saylor

Guest surface exposes syllabi/chrome only; unit readings require enrollment → **excluded** with reason `unit_materials_require_enrollment_not_ingested`. AI Learning Zone excluded (`nc_license_marker`). Certificate/Translation chrome excluded. Included: course-specific syllabi/intros under CC BY.

Evidence: `docs/delivery/saylor-provenance-filter-evidence.json`, ingest-time `provenance_filter` metadata.

## Phase 3 — Gov / signals

- FTC CAN-SPAM / endorsements / native / advertising basics — refreshable A
- SBA market research / business plan / customers — A
- Census — structured dimensions doc (+ optional ACS sample if `CENSUS_API_KEY`)
- Google Trends — access status reported honestly; live research fallback

## Phase 4 — NC gate + HubSpot

Disposable NC attempt must reject with `commercial_use_allowed` error. HubSpot/Trends `assert_ingest_allowed` raises type D refuse.

## Phase 5 — Router

CAN-SPAM / FTC / endorsement queries route **Marketing + Legal**. Authority rerank: FTC (~0.99) > Saylor (~0.84) > HubSpot live (~0.55).

## Evidence pointers

- Unit tests: `pytest tests/knowledge_fabric/` → **13 passed** (schema lint + router/authority + NC gate)
- NC gate live: `nc_gate_ingest.rejected=true` @ `2026-08-11T17:58:34Z` in `sales-marketing-packs-ingest-live.json`
- Ingest live: marketing **15 docs / 65 chunks**, sales **2 docs / 6 chunks**, errors `[]`
- Retrieve live @ `2026-08-11T18:01:21Z`: FTC CAN-SPAM → FTC citations authority 0.99; market research → SBA citations authority 0.90 (`sales-marketing-retrieve-live.json`)
- Saylor provenance: `saylor-provenance-filter-evidence.json` + ingest metadata `provenance_filter`
- Stale holds `sales.content.hold` / `marketing.content.hold` **retired** in prod
- Deploy tip: `GET https://api.gravitre.app/health` → `git_sha=a171ed8c0b9a6f2699d520471438efcbde0bfab4` (tip of this ship)
