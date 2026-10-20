-- Part 5 of the storage migration (see 20261020081535_storage_retention_metering.sql).

CREATE OR REPLACE FUNCTION public.data_retention_fetch_batch(
  p_table text,
  p_org_id uuid,
  p_cutoff timestamptz,
  p_batch int DEFAULT 1000
) RETURNS SETOF jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_floor int := public.data_retention_floor_days(p_table);
  v_batch int := least(greatest(coalesce(p_batch, 1000), 1), 10000);
BEGIN
  IF v_floor IS NULL THEN
    RAISE EXCEPTION 'data_retention: table % is not eligible', p_table;
  END IF;
  IF p_cutoff IS NULL OR p_cutoff > now() - make_interval(days => v_floor) THEN
    RAISE EXCEPTION 'data_retention: cutoff for % is inside the % day floor', p_table, v_floor;
  END IF;
  IF p_org_id IS NULL OR to_regclass(format('public.%I', p_table)) IS NULL THEN
    RETURN;
  END IF;
  IF EXISTS (SELECT 1 FROM public.org_legal_holds h
              WHERE h.org_id = p_org_id AND h.released_at IS NULL) THEN
    RETURN;
  END IF;
  RETURN QUERY EXECUTE format(
    'SELECT to_jsonb(t)
       FROM public.%I t
      WHERE t.org_id = $1 AND t.created_at < $2 %s
      ORDER BY t.created_at, t.id
      LIMIT $3',
    p_table, public.data_retention_where(p_table)
  ) USING p_org_id, p_cutoff, v_batch;
END;
$$;

REVOKE ALL ON FUNCTION public.data_retention_fetch_batch(text, uuid, timestamptz, int)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.data_retention_fetch_batch(text, uuid, timestamptz, int) TO service_role;
