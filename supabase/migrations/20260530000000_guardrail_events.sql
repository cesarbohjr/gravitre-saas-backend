-- GRAVITRE AI guardrail / failover event log
-- Records multi-provider failover attempts (providers tried, outcomes, final
-- provider, latency) and other guardrail events for observability.

CREATE TABLE IF NOT EXISTS guardrail_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    detail JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_guardrail_events_org_created
    ON guardrail_events (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_guardrail_events_type
    ON guardrail_events (event_type);
