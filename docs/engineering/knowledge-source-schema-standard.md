# Knowledge source schema standard

**Companion to:** connector-action schema standard (G.2/G.4 process pattern only — not ActionSpec).  
**Enforcement:** `backend/tests/knowledge_fabric/test_knowledge_source_schema_lint.py`

## Object identity

A knowledge source is a **corpus provenance record**, not an invoke tool. It must not be registered in `ActionSpec` / `all_catalog_action_specs()`.

## Required metadata (every shipped source)

| Field | Rule |
| -- | -- |
| `source_id` | Stable slug (`legal.courtlistener.opinions`, …) |
| `publisher` | Real publisher name |
| `url` | Canonical source URL |
| `source_type` | One of registry types (api, government_work, …) |
| `department` | Primary department pack |
| `license_type` | **A \| B \| C \| D \| E** (see below) |
| `commercial_use_allowed` | Boolean consistent with license |
| `attribution_required` | Boolean |
| `crawl_allowed` | Boolean — false for type D |
| `ingestion_method` | `api` \| `bulk` \| `manual_authored` \| `live_only` |
| `refresh_frequency` | `realtime` \| `daily` \| `weekly` \| `version_change` \| `manual` |
| `authority_score` | 0.0–1.0 |
| `quality_score` | 0.0–1.0 |
| `topics` | Non-empty list |
| `jurisdictions` | List (may be empty for non-legal) |

## License classification (non-negotiable)

| Code | Meaning | Store permanently? |
| -- | -- | -- |
| **A** | Open / public-domain / explicitly reusable (e.g. U.S. government works in the U.S.) | Yes |
| **B** | API-licensed — connect per the API’s real terms | Yes, within terms |
| **C** | Commercially licensed — confirmed license required first | Only after license |
| **D** | Public web, unclear reuse — live on-demand only | **Never** |
| **E** | Customer-owned — that tenant only | Private RAG only |

No source ships without a complete A–E classification. Type D must set `ingestion_method=live_only` and `crawl_allowed=false`.

## Document / chunk fields

Documents: `published_at`, `effective_at`, `superseded_at`, `checksum`, versioning.  
Chunks: embedding (1536 OpenAI path), topics, jurisdiction, `authority_score`, `freshness_score`, citation string.
