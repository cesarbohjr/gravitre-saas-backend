-- MCP server execution has its own identity domain.
-- connector_rate_limits.connector_id is FK'd to connectors(id) and MUST NOT
-- accept mcp_servers(id). Keep both token buckets atomic and fail closed.
BEGIN;

CREATE TABLE IF NOT EXISTS public.mcp_server_rate_limits (
    org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    server_id uuid NOT NULL REFERENCES public.mcp_servers(id) ON DELETE CASCADE,
    step_type text NOT NULL,
    capacity numeric NOT NULL CHECK (capacity > 0),
    refill_per_sec numeric NOT NULL CHECK (refill_per_sec >= 0),
    tokens numeric NOT NULL CHECK (tokens >= 0),
    last_refill timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, step_type, server_id)
);

ALTER TABLE public.mcp_server_rate_limits ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.mcp_server_rate_limits FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.mcp_server_rate_limits TO service_role;

CREATE OR REPLACE FUNCTION public.consume_mcp_server_token(
    p_org_id uuid,
    p_server_id uuid,
    p_step_type text,
    p_capacity numeric,
    p_refill_per_sec numeric
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $function$
DECLARE
    v_now timestamptz := clock_timestamp();
    v_tokens numeric;
    v_last_refill timestamptz;
    v_allowed boolean := false;
BEGIN
    IF p_org_id IS NULL OR p_server_id IS NULL OR p_step_type IS NULL
       OR p_capacity IS NULL OR p_refill_per_sec IS NULL
       OR p_capacity <= 0 OR p_refill_per_sec < 0 THEN
        RETURN false;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.mcp_servers
        WHERE id = p_server_id AND org_id = p_org_id AND enabled = true
    ) THEN
        RETURN false;
    END IF;

    INSERT INTO public.mcp_server_rate_limits (
        org_id, server_id, step_type, capacity, refill_per_sec,
        tokens, last_refill, updated_at
    ) VALUES (
        p_org_id, p_server_id, p_step_type, p_capacity, p_refill_per_sec,
        p_capacity, v_now, v_now
    )
    ON CONFLICT (org_id, step_type, server_id) DO NOTHING;

    SELECT tokens, last_refill INTO v_tokens, v_last_refill
    FROM public.mcp_server_rate_limits
    WHERE org_id = p_org_id AND step_type = p_step_type AND server_id = p_server_id
    FOR UPDATE;

    IF NOT FOUND THEN RETURN false; END IF;
    v_tokens := LEAST(p_capacity, v_tokens +
        GREATEST(0, EXTRACT(EPOCH FROM (v_now - v_last_refill))) * p_refill_per_sec);
    IF v_tokens >= 1 THEN
        v_tokens := v_tokens - 1;
        v_allowed := true;
    END IF;

    UPDATE public.mcp_server_rate_limits
    SET tokens = v_tokens,
        capacity = p_capacity,
        refill_per_sec = p_refill_per_sec,
        last_refill = v_now,
        updated_at = v_now
    WHERE org_id = p_org_id AND step_type = p_step_type AND server_id = p_server_id;

    RETURN v_allowed;
END;
$function$;

REVOKE ALL ON FUNCTION public.consume_mcp_server_token(uuid,uuid,text,numeric,numeric)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.consume_mcp_server_token(uuid,uuid,text,numeric,numeric)
    TO service_role;

COMMIT;
