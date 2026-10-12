-- Phase 1 memory correctness: vector recall must not return superseded or expired rows.
--
-- agent_memory_search (last defined in 20260708160300) and
-- agent_memory_search_by_department (last defined in 20260813160000) predate the
-- temporal hardening in 20260903120000, which added is_current and documents that
-- "recall paths must filter is_current=true". Neither RPC did, and the department
-- RPC never checked expires_at either.
--
-- Bodies, signatures, return types and security mode (invoker, STABLE sql) are
-- copied unchanged from those definitions; only the WHERE clauses gain
-- coalesce(is_current, true) and, for the department RPC, the expiry check.

CREATE OR REPLACE FUNCTION public.agent_memory_search(
  p_org_id uuid,
  p_agent_id uuid,
  p_query_embedding text,
  p_top_k int,
  p_category text DEFAULT NULL
)
RETURNS TABLE (
  memory_id uuid,
  content text,
  category text,
  provenance text,
  confidence numeric,
  usage_count int,
  editable boolean,
  score float,
  created_at timestamptz
)
LANGUAGE sql
STABLE
AS $$
  SELECT
    m.id AS memory_id,
    m.content,
    m.category,
    m.provenance,
    m.confidence,
    m.usage_count,
    m.editable,
    (1 - (m.embedding <=> (p_query_embedding::vector(1536))))::float AS score,
    m.created_at
  FROM public.agent_memories m
  WHERE m.org_id = p_org_id
    AND m.agent_id = p_agent_id
    AND m.embedding IS NOT NULL
    AND m.is_active IS TRUE
    AND coalesce(m.is_current, true)
    AND (m.expires_at IS NULL OR m.expires_at > now())
    AND (p_category IS NULL OR m.category = p_category)
  ORDER BY m.embedding <=> (p_query_embedding::vector(1536))
  LIMIT p_top_k;
$$;

CREATE OR REPLACE FUNCTION public.agent_memory_search_by_department(
  p_org_id uuid,
  p_department_id uuid,
  p_query_embedding text,
  p_top_k int,
  p_category text DEFAULT NULL
)
RETURNS TABLE (
  memory_id uuid,
  content text,
  category text,
  provenance text,
  confidence numeric,
  usage_count int,
  editable boolean,
  agent_id uuid,
  department_id uuid,
  score float,
  created_at timestamptz
)
LANGUAGE sql
STABLE
AS $$
  SELECT
    m.id AS memory_id,
    m.content,
    m.category,
    m.provenance,
    m.confidence,
    m.usage_count,
    m.editable,
    m.agent_id,
    m.department_id,
    (1 - (m.embedding <=> (p_query_embedding::vector(1536))))::float AS score,
    m.created_at
  FROM public.agent_memories m
  WHERE m.org_id = p_org_id
    AND m.department_id = p_department_id
    AND m.embedding IS NOT NULL
    AND (p_category IS NULL OR m.category = p_category)
    AND COALESCE(m.is_active, true) = true
    AND coalesce(m.is_current, true)
    AND (m.expires_at IS NULL OR m.expires_at > now())
  ORDER BY m.embedding <=> (p_query_embedding::vector(1536))
  LIMIT p_top_k;
$$;
