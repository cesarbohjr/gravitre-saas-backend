# Workflow disaster recovery runbook (STA-95)

## Targets

| Metric | Target |
|--------|--------|
| RPO (workflow definitions + run state) | 15 minutes |
| RTO (restore + resume queue) | 60 minutes |

## Backup scope

1. `workflow_defs` — definitions and step graphs
2. `workflow_runs` + `workflow_run_steps` — in-flight and recent history
3. `agent_jobs` — durable async operator jobs
4. Redis queue keys: `gravitre:workflow-runs`, `gravitre:agent-execution`

## Quarterly drill checklist

1. Export latest workflow definitions for one pilot org.
2. Snapshot Supabase tables listed above.
3. Verify `REDIS_URL` persistence/replication settings in Railway.
4. Restore workflow defs into staging org and run dry-run.
5. Enqueue a test workflow run via Redis queue and confirm worker pickup.
6. Document actual RPO/RTO observed and open follow-ups in Linear.

## Failover steps

1. Pause schedulers (`workflow_schedules` worker).
2. Drain Redis queues or mark stale runs failed with audit note.
3. Promote read replica / restore Supabase backup to primary.
4. Redeploy API + workers from last known good commit.
5. Replay queued jobs idempotently using run idempotency keys.
6. Re-enable schedulers and monitor `/api/metrics/overview`.

## Contacts

- Platform on-call: `#gravitre-platform`
- Supabase support: project dashboard
- Railway support: service dashboard
