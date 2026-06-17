-- MKT-10.1: Atomic install_count / clone_count increments for marketplace analytics.

CREATE OR REPLACE FUNCTION public.increment_marketplace_asset_counter(
  p_asset_id uuid,
  p_counter text
)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  new_value integer;
BEGIN
  IF p_counter NOT IN ('install_count', 'clone_count') THEN
    RAISE EXCEPTION 'invalid counter: %', p_counter;
  END IF;

  IF p_counter = 'install_count' THEN
    UPDATE public.marketplace_assets
    SET install_count = install_count + 1,
        updated_at = now()
    WHERE id = p_asset_id
    RETURNING install_count INTO new_value;
  ELSE
    UPDATE public.marketplace_assets
    SET clone_count = clone_count + 1,
        updated_at = now()
    WHERE id = p_asset_id
    RETURNING clone_count INTO new_value;
  END IF;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'asset not found: %', p_asset_id;
  END IF;

  RETURN new_value;
END;
$$;

REVOKE ALL ON FUNCTION public.increment_marketplace_asset_counter(uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.increment_marketplace_asset_counter(uuid, text) TO service_role;

COMMENT ON FUNCTION public.increment_marketplace_asset_counter IS
  'Atomically bump marketplace_assets.install_count or clone_count (MKT-10.1).';
