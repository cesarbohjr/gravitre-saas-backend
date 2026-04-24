# Phase 9: AI Operator Power Features

## Operator Feature Capability Review

### What data already exists

- **Runs + steps + approvals**: `/api/workflows/runs/:id` returns run metadata, steps, approval status, and counts. Pending approvals list is available. (`backend/app/routers/workflows.py`)
- **Workflows + versions**: workflow definitions, active versions, and version history are available. (`backend/app/routers/workflows.py`)
- **Connectors**: connector list and detail endpoints exist; secrets are write-only. (`backend/app/routers/connectors.py`)
- **Sources + documents + ingest**: RAG sources, documents, and ingest job status are available via admin RAG endpoints. (`backend/app/routers/rag_admin.py`)
- **Audit**: audit query API supports resource-scoped timelines. (`backend/app/routers/audit.py`)
- **Policy + guardrails**: policy engine and workflow policy resolution enforce approvals and environment/role constraints. (`backend/app/policy/engine.py`, `backend/app/workflows/policy.py`)
- **Environment scoping**: `X-Environment` header is enforced across org-scoped routes. (`backend/app/auth/dependencies.py`)

### What can be reused

- Existing entity APIs provide the raw facts for operator context packs.
- Policy engine + workflow policy resolution can supply approval/admin requirements for action plans.
- Audit query can provide safe event summaries for run context.

### Minimal new backend aggregation required

- A thin operator aggregation layer under `/api/v1/operator/*` that composes existing data into concise, operator-facing context packs.
- A deterministic action-plan endpoint that returns steps with explicit explainability and guardrail labels (no execution).

