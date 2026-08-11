# Knowledge Fabric Wave 2 — Phase 0 dedupe (2026-08-11)

Live query: `knowledge_sources` @ Supabase `smyeexlrqdpymwjmgzqu` (platform_shared).

## Already live — do not re-ingest

| Proposed | Live `source_id` | Docs/Chunks | Notes |
| -- | -- | -- | -- |
| FTC guidance | `marketing.ftc.business_guidance` | 4 / 16 | verified_live, weekly |
| SBA guidance | `marketing.sba.guidance` | 2 / 12 | verified_live |
| Census API | `sales.census.api` | 1 / 1 | structured catalog stub only |
| Saylor Sales Management | `sales.saylor.bus633` | 1 / 5 | syllabi-only filter |
| Saylor Strategic Marketing | `marketing.saylor.bus502` | 2 / 6 | syllabi-only |
| Saylor Consumer Behavior | `marketing.saylor.bus630` | 1 / 5 | syllabi-only |
| Saylor Marketing Research | `marketing.saylor.bus634` | 1 / 5 | syllabi-only |
| NIST CSF | `cyber.nist.csf2` | 3 / 3 | + `cyber.nist.sp800-53` also live |
| SEC EDGAR | `finance.sec.edgar` | 2 / 2 | **submissions / sample filings path** — not Company Facts / Frames APIs |

Also live (related, not in proposal list): US Constitution; DOL FLSA/FMLA overview (`hr.dol.developer`); other Saylor syllabi (BUS203/631/632/615); Google Trends + HubSpot type D; OpenStax paused `blocked_nc`.

## Redirect to connector catalog (not KF RAG) — Phase 3 only

World Bank Indicators · FRED · OECD Data Explorer · SEC **Frames / Company Facts** · BLS · Census **dimensional** query APIs  
→ ActionSpec candidates. **No `knowledge_chunks` ingest in this pass.**

## Genuinely new — Wave 2 KF ingest list (Phase 2)

1. **HR** — DOL Employment Law Guide (REFRESH; expands beyond current FLSA/FMLA snippets)
2. **HR** — EEOC Employer Guidance + Guidance Library (REFRESH)
3. **Legal CA** — Justice Laws Canada Acts / Regulations / XML corpus (REFRESH/FULL) — **new jurisdiction**
4. **Cyber** — NIST AI RMF (FULL/REFRESH)
5. **Cyber** — NIST GenAI Profile (FULL/REFRESH)
6. **Cyber** — NIST Zero Trust Architecture SP 800-207 (FULL/REFRESH)
7. **Cyber** — CISA Advisories (REFRESH)
8. **Cyber** — CISA MSP Guidance (REFRESH)
9. **Cyber** — CISA StopRansomware (REFRESH)
10. **Marketing CA** — Competition Bureau Canada deceptive + influencer marketing guidance (REFRESH)

## Explicitly not in this pass

OpenStax (blocked) · Saylor unit readings (blocked) · Executive/Strategy pack · Procurement/GTM · industry packs · paid methodology.
