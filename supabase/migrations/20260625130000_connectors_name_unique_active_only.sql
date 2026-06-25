-- Allow reusing connector names after soft-delete (fixes API-key connect for names like "apollo").
DROP INDEX IF EXISTS public.connectors_org_name_key;

CREATE UNIQUE INDEX connectors_org_name_key
  ON public.connectors (org_id, name)
  WHERE deleted_at IS NULL;
