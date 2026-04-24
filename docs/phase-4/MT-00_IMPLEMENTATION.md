# MT-00 — Metrics Aggregation API

**Status:** Implemented  
**Authority:** docs/MASTER_PHASED_MODULE_PLAN.md Part V  
**Data Sources:** workflow_runs, workflow_steps, audit_events, rag_retrieval_logs, rag_ingest_jobs

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/metrics/overview | Overview cards |
| GET | /api/metrics/workflows | Workflow funnel + reliability |
| GET | /api/metrics/rag | RAG usage + latency + ingestion |
| GET | /api/metrics/connectors | Connector delivery stats |
| GET | /api/metrics/timeseries | Daily buckets for charts |

**Range param:** `range=7d|30d|90d` (default 7d).  
Org is derived from auth; no org_id accepted from client.

---

## Response Shapes (Highlights)

### /overview
- workflows: dry_runs_total, exec_runs_total, exec_success_rate, pending_approvals  
- rag: retrieval_requests_total, avg_latency_ms, p95_latency_ms, avg_result_count, insufficient_data  
- ingestion: ingest_jobs_total, ingest_success_rate, chunks_embedded_total  
- connectors: slack_sent, email_sent, webhook_sent, send_failures_total  

### /workflows
- exec.by_status (pending_approval, running, completed, failed, cancelled)  
- exec.approval_funnel (created, approved, rejected)  
- exec.avg_duration_ms, exec.p95_duration_ms  
- exec.step_failures_by_type  
- dry_run.total, dry_run.rag_step_failure_rate  

### /rag
- retrieval.total, avg_latency_ms, p95_latency_ms, avg_result_count, zero_result_rate  
- ingestion.jobs_total, by_status, avg_chunks_per_job, p95_chunks_per_job  

### /connectors
- slack/email/webhook sent/failed counts  

### /timeseries
Supported metrics: exec_runs_total, exec_failures_total, rag_retrieval_total, ingest_jobs_total, connector_sends_total

---

## Privacy Guarantees

No PII returned. No query text, message text, payloads, or secrets are included in responses.

---

## Performance Notes

- Uses org‑scoped aggregate queries with range filters.
- Percentiles computed in memory from result sets for the selected range.
*** End Patch"]}"}}
