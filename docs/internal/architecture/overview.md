---
title: Platform architecture (internal)
description: Engineering overview of Gravitre subsystems and data flow — internal audience only.
audience: internal
depth: deep
tier: all
status: published
category: Architecture
readTime: 15 min
---

> **Internal only.** Do not republish externally. Describes structure, not proprietary algorithms.

## Subsystems

| Subsystem | Location | Role |
|-----------|----------|------|
| Web app | `apps/web` | Next.js UI, marketing, docs, settings |
| API | `backend/app` | FastAPI routers, auth, billing gate |
| Workers | `backend/app/workers` | Workflow runs, training, async jobs |
| Connectors | `backend/app/connectors` | OAuth, tool executors, vendor SDK |
| Agents | `backend/app/operators` | Operator runtime, ReAct, tool calls |
| RAG | `backend/app/rag` | Ingest, retrieve, knowledge sync |

## Request flow (simplified)

```text
Browser → gravitre.app (/api rewrite) → FastAPI → Postgres (Supabase)
                                      → external vendor APIs
                                      → LLM providers
```

## What belongs in internal docs

- Router maps, worker topology, deployment runbooks
- Connector smoke tests and env var registries
- Compliance evidence mapping

## What stays out of docs

- Model routing weights, guardrail prompt text, proprietary ranking logic
- Secrets, bypass tokens, raw credentials

## Related repos paths

- Route entitlements: `docs/delivery/route-entitlement-classification.json`
- Connector matrix: `docs/CONNECTOR_IMPLEMENTATION_MATRIX.md`
- Public docs source: `apps/web/content/docs/public/`
