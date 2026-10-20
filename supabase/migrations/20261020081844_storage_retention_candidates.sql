-- Part 4 of the storage migration (see 20261020081535_storage_retention_metering.sql).

CREATE OR REPLACE FUNCTION public.data_retention_candidates(
  p_table text,
  p_cutoff timestamptz
) RETURNS TABLE (org_id uuid, row_count bigint)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_floor int := public.data_retention_floor_days(p_table);
BEGIN
  IF v_floor IS NULL THEN
    RAISE EXCEPTION 'data_retention: table % is not eligible', p_table;
  END IF;
  IF p_cutoff IS NULL OR p_cutoff > now() - make_interval(days => v_floor) THEN
    RAISE EXCEPTION 'data_retention: cutoff for % is inside the % day floor', p_table, v_floor;
  END IF;
  IF to_regclass(format('public.%I', p_table)) IS NULL THEN
    RETURN;
  END IF;
  RETURN QUERY EXECUTE format(
    'SELECT t.org_id, count(*)::bigint
       FROM public.%I t
      WHERE t.created_at < $1 %s
        AND NOT EXISTS (
          SELECT 1 FROM public.org_legal_holds h
           WHERE h.org_id = t.org_id AND h.released_at IS NULL)
      GROUP BY t.org_id
      ORDER BY t.org_id',
    p_table, public.data_retention_where(p_table)
  ) USING p_cutoff;
END;
$$;

REVOKE ALL ON FUNCTION public.data_retention_candidates(text, timestamptz) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.data_retention_candidates(text, timestamptz) TO service_role;
