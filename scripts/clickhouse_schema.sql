-- ClickHouse analytics schema (run against ClickHouse, NOT Supabase/Postgres)

CREATE DATABASE IF NOT EXISTS gravitre;

CREATE TABLE IF NOT EXISTS gravitre.pipeline_events (
  org_id UUID,
  message_id UUID,
  stage_name LowCardinality(String),
  tier LowCardinality(String),
  duration_ms UInt32,
  cache_hit Bool,
  model_used LowCardinality(String),
  cost_usd Float32,
  created_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (org_id, created_at, stage_name);

CREATE TABLE IF NOT EXISTS gravitre.outcome_events (
  org_id UUID,
  agent_id UUID,
  workflow_run_id UUID,
  action_type LowCardinality(String),
  metric_name LowCardinality(String),
  metric_before Float64,
  metric_after Float64,
  delta Float64,
  attribution_window_days UInt8,
  created_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (org_id, created_at, metric_name);

CREATE TABLE IF NOT EXISTS gravitre.mcp_executions (
  org_id UUID,
  tool_id UUID,
  capability_tier LowCardinality(String),
  status LowCardinality(String),
  latency_ms UInt32,
  created_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (org_id, created_at);
