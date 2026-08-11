# Knowledge Fabric Wave 2 — closeout (2026-08-11)

## Phase 0 — Dedupe

See `docs/delivery/knowledge-fabric-wave2-phase0-dedupe.md`. Already-live sources (FTC, SBA, Census stub, Saylor syllabi, NIST CSF/SP800-53, SEC EDGAR submissions path) were **not** re-ingested.

## Phase 1 — Schema + gates

- Migration `20260811220000_knowledge_sources_wave2_metadata.sql` applied to prod Supabase `smyeexlrqdpymwjmgzqu`
- Columns: `licence_verified`, `license_verified_at`, retrieval flags, `refresh_days`, `effective_date_sensitive`
- Hard gate: `licence_verified=true` required in `assert_ingest_allowed` + DB CHECK for active A/B
- Saylor resource allow/block: CC-BY(-SA) 3.0/4.0 allow; NC/ARR/UNKNOWN block

## Phase 2 — Ingest (live license verify first)

| Source | License family | Verified | Docs | Chunks | Notes |
| -- | -- | -- | -- | -- | -- |
| `hr.dol.employment_law_guide` | US-Gov-Work | yes @ usa.gov/government-copyright | 2 | 12 | |
| `hr.eeoc.employer_guidance` | US-Gov-Work | yes | 3 | 15 | |
| `legal.ca.justice_laws` | Canada-OGL | yes @ open.canada.ca OGL | 3 | 9 | New jurisdiction `CA-federal` |
| `cyber.nist.ai_rmf` | US-Gov-Work | yes | 1 | 1 | |
| `cyber.nist.genai_profile` | US-Gov-Work | yes | 1 | 1 | |
| `cyber.nist.zero_trust` | US-Gov-Work | yes | 1 | 1 | |
| `cyber.cisa.advisories` | US-Gov-Work | yes | 3 | 3 | Live HTML **403** from Akamai; curated summaries with `fetch_status` metadata |
| `marketing.ca.competition_bureau` | Canada-OGL | yes | 1 | 2 | 1 of 3 URLs returned usable content |

Artifact: `docs/delivery/knowledge-fabric-wave2-ingest-results.json`  
First US-Gov probe attempt halted (usa.gov meta-refresh / flaky fetch) — correctly blocked until live match; re-verify passed then ingest proceeded.

## Router US vs CA (live)

`docs/delivery/knowledge-fabric-wave2-router-reverify.json` @ `2026-08-11T20:26:14Z`:

- US Constitution query → jurisdictions `US-federal` only; hits `US-FEDERAL` only; `us_excludes_ca=true`
- PIPEDA / Justice Laws Canada → `CA-federal` only; hits `CA-FEDERAL` only from `legal.ca.justice_laws`; `ca_excludes_us_federal=true`
- Vector path previously leaked CA into US queries — fixed via shared `jurisdiction_allowed()` on FTS + vector

## Phase 3 — Connector feasibility (no build)

`docs/delivery/knowledge-fabric-wave2-phase3-connector-feasibility.md` — World Bank / FRED / OECD / SEC Facts·Frames / BLS / Census dimensional → ActionSpec initiative, not KF RAG.

## Phase 4 — Quality dashboard

- API: `GET /api/knowledge-fabric/admin/quality` (platform admin)
- UI: Admin Intelligence overview → **Knowledge Fabric quality** card
- Metrics: topic coverage %, authoritative/primary counts, avg authority, freshness days, jurisdictions, live-provider count, citation %, license-verified %, named gaps

## Deploy

- Commit / tip: `d59cb0d075d46eacb4bd57846657a6eb82191a09`
- Pushed `main` → Railway
- Live `GET https://api.gravitre.app/health` → `git_sha=d59cb0d075d46eacb4bd57846657a6eb82191a09` `status=ok` (polled after prior tip `4a3c9731`)

Corpus + router evidence above was written against live Supabase before/during deploy; jurisdiction filter ships in this tip.

## Deferred (unchanged)

Executive/Strategy pack · Procurement/GTM · industry packs · MEDDPICC
