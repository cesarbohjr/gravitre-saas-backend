# Knowledge Fabric Wave 2 — Phase 3 connector feasibility (no build)

**Decision:** structured/API dimensional sources are **ActionSpec / AgentToolSpec** candidates, not `knowledge_chunks` RAG. Same G.2/G.4 schema, CI lint, narrowing, and governance as the existing ~696-action catalog. **No connector code in this pass.**

## Candidates

| Source | Why not KF RAG | Feasible connector actions (examples) | Effort | Notes |
| -- | -- | -- | -- | -- |
| World Bank Indicators | Time-series / queryable metrics | `worldbank.get_indicator`, `worldbank.get_gdp_growth` | M | Free API; country+indicator+year params; rate limits |
| FRED (St. Louis Fed) | Macro series | `fred.get_series`, `fred.get_observations` | M | API key; attribution; series_id required |
| OECD Data Explorer | Multidimensional SDMX | `oecd.get_dataset`, `oecd.get_observation` | L | SDMX complexity; narrow to 3–5 high-value datasets first |
| SEC Company Facts / Frames | Structured XBRL facts | `sec.get_company_facts`, `sec.get_frames` | M | EDGAR submissions already in KF; Facts/Frames are live tools, not packs |
| BLS | Labor statistics series | `bls.get_series`, `bls.get_industry_employment` | M | Registration key; series IDs |
| Census dimensional | ACS / CBP / BDS query APIs | `census.get_acs`, `census.get_business_formations`, `census.get_establishments` | M–L | Catalog stub already in KF (`sales.census.api`); dimensional pulls belong here |

## Scope recommendation (separate initiative)

1. **Pilot 6–10 actions** across FRED + Census + SEC Company Facts (highest sales/finance overlap).
2. Reuse existing connector registry patterns: ActionSpec JSON, CI lint, org credential vault, audit `tool.invoke.*`.
3. Do **not** duplicate SEC EDGAR narrative filings already in `finance.sec.edgar` knowledge pack.
4. Estimated: 1–2 engineering weeks for pilot + governance wiring; OECD deferred to wave after pilot.

## Explicit non-goals this pass

- No ActionSpec files authored
- No CI catalog expansion
- No knowledge_chunks for these APIs
