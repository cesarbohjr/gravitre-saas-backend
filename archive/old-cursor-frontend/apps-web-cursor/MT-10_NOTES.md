# MT-10 — Metrics UI Notes

## Routes
- `/metrics` — dashboard with overview, workflows, RAG, integrations, ingestion, and trend table

## Proxy routes (same-origin)
- `/api/metrics/overview`
- `/api/metrics/workflows`
- `/api/metrics/rag`
- `/api/metrics/integrations`
- `/api/metrics/timeseries`

## Range behavior
- Range selector: 7d / 30d / 90d (default 7d)
- All requests include `range` query param

## Privacy
No PII displayed. No emails, message text, webhook URLs, query text, or chunk text.
