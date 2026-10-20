-- Part 9 of the storage migration (see 20261020081535_storage_retention_metering.sql).
-- Applied by the owner (supabase db push) because the migration tool waits for a
-- confirmation on statements containing DELETE.

-- Deletes at most p_batch rows of one org, oldest first. With p_ids (archive mode) only
-- those ids are deleted, and only while they still match every predicate.
CREATE OR REPLACE FUNCTION public.data_retention_delete_batch(
  p_table text,
  p_org_id uuid,
  p_cutoff timestamptz,
  p_batch int DEFAULT 1000,
  p_ids uuid[] DEFAULT NULL
) RETURNS int
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_floor int := public.data_retention_floor_days(p_table);
  v_batch int := least(greatest(coalesce(p_batch, 1000), 1), 10000);
  v_deleted int := 0;
BEGIN
  IF v_floor IS NULL THEN
    RAISE EXCEPTION 'data_retention: table % is not eligible', p_table;
  END IF;
  IF p_cutoff IS NULL OR p_cutoff > now() - make_interval(days => v_floor) THEN
    RAISE EXCEPTION 'data_retention: cutoff for % is inside the % day floor', p_table, v_floor;
  END IF;
  IF p_org_id IS NULL OR to_regclass(format('public.%I', p_table)) IS NULL THEN
    RETURN 0;
  END IF;
  IF EXISTS (SELECT 1 FROM public.org_legal_holds h
              WHERE h.org_id = p_org_id AND h.released_at IS NULL) THEN
    RETURN 0;
  END IF;
  IF p_ids IS NOT NULL THEN
    IF cardinality(p_ids) > 10000 THEN
      RAISE EXCEPTION 'data_retention: at most 10000 ids per batch';
    END IF;
    EXECUTE format(
      'DELETE FROM public.%I t
        WHERE t.id = ANY($3) AND t.org_id = $1 AND t.created_at < $2 %s',
      p_table, public.data_retention_where(p_table)
    ) USING p_org_id, p_cutoff, p_ids;
  ELSE
    EXECUTE format(
      'WITH doomed AS (
         SELECT t.id FROM public.%I t
          WHERE t.org_id = $1 AND t.created_at < $2 %s
          ORDER BY t.created_at, t.id
          LIMIT $3
          FOR UPDATE SKIP LOCKED)
       DELETE FROM public.%I d USING doomed WHERE d.id = doomed.id',
      p_table, public.data_retention_where(p_table), p_table
    ) USING p_org_id, p_cutoff, v_batch;
  END IF;
  GET DIAGNOSTICS v_deleted = ROW_COUNT;
  RETURN v_deleted;
END;
$$;

REVOKE ALL ON FUNCTION public.data_retention_delete_batch(text, uuid, timestamptz, int, uuid[])
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.data_retention_delete_batch(text, uuid, timestamptz, int, uuid[])
  TO service_role;
