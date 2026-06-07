# Gravitre Enterprise Helm deployment (STA-85)

Single-tenant / VPC deployment chart for web + API + workers.

## Prerequisites

- Kubernetes 1.28+
- Helm 3.14+
- Supabase-compatible Postgres (managed or self-hosted)
- Redis for durable queues (`REDIS_URL`)

## Install

```bash
helm upgrade --install gravitre ./deploy/enterprise/helm \
  --namespace gravitre \
  --create-namespace \
  -f values.production.yaml
```

## Components

| Chart service | Role |
|---------------|------|
| `api` | FastAPI backend |
| `web` | Next.js frontend |
| `worker` | Agent job + workflow queue consumer |
| `redis` | Optional in-cluster Redis (disable when using managed Redis) |

## Required secrets

- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`
- `CONNECTOR_SECRETS_ENCRYPTION_KEY`
- `OPENAI_API_KEY`
- Connector OAuth env vars from `backend/.env.example`

## Security hardening

- Run pods as non-root
- NetworkPolicy: API ↔ Postgres/Redis only
- Rotate `CONNECTOR_SECRETS_ENCRYPTION_KEY` only with migration plan
- Enable org data residency before multi-region rollout

See `docs/integration/TIER4_PRODUCTION_SMOKE.md` for verification steps.
