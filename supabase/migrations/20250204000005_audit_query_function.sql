-- BE-12: Read-only audit query with cursor pagination (seek on created_at, id).
-- No new tables; uses existing audit_events from BE-11.

CREATE OR REPLACE FUNCTION public.audit_query(
  p_org_id uuid,
  p_resource_type text,
  p_resource_id uuid,
  p_limit int,
  p_cursor_created_at timestamptz DEFAULT NULL,
  p_cursor_id uuid DEFAULT NULL,
  p_action_prefix text DEFAULT NULL
)
RETURNS TABLE (
  id uuid,
  action text,
  actor_id uuid,
  resource_type text,
  resource_id uuid,
  metadata jsonb,
  created_at timestamptz
)
LANGUAGE sql
STABLE
AS $$
  SELECT
    e.id,
    e.action,
    e.actor_id,
    e.resource_type,
    e.resource_id,
    e.metadata,
    e.created_at
  FROM public.audit_events e
  WHERE e.org_id = p_org_id
    AND e.resource_type = p_resource_type
    AND e.resource_id = p_resource_id
    AND (p_action_prefix IS NULL OR e.action LIKE p_action_prefix || '%')
    AND (
      p_cursor_created_at IS NULL AND p_cursor_id IS NULL
      OR (e.created_at, e.id) < (p_cursor_created_at, p_cursor_id)
    )
  ORDER BY e.created_at DESC, e.id DESC
  LIMIT p_limit;
$$;
