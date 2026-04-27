CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TABLE IF NOT EXISTS public.connectors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  type text NOT NULL,
  status text NOT NULL DEFAULT 'disconnected',
  environment text NOT NULL DEFAULT 'production',
  last_sync timestamptz,
  health integer NOT NULL DEFAULT 0,
  description text,
  data_flow_rate text,
  requests_today integer NOT NULL DEFAULT 0,
  latency integer NOT NULL DEFAULT 0,
  category text,
  auth_type text,
  used_by_workflows integer NOT NULL DEFAULT 0,
  triggered_by_agents integer NOT NULL DEFAULT 0,
  config jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.connectors
  ADD COLUMN IF NOT EXISTS environment text NOT NULL DEFAULT 'production',
  ADD COLUMN IF NOT EXISTS data_flow_rate text,
  ADD COLUMN IF NOT EXISTS requests_today integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS latency integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS used_by_workflows integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS triggered_by_agents integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'connectors_status_check'
  ) THEN
    ALTER TABLE public.connectors
      ADD CONSTRAINT connectors_status_check
      CHECK (status IN ('connected', 'disconnected', 'error', 'syncing'));
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'connectors_environment_check'
  ) THEN
    ALTER TABLE public.connectors
      ADD CONSTRAINT connectors_environment_check
      CHECK (environment IN ('production', 'staging'));
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'connectors_auth_type_check'
  ) THEN
    ALTER TABLE public.connectors
      ADD CONSTRAINT connectors_auth_type_check
      CHECK (auth_type IS NULL OR auth_type IN ('oauth', 'apiKey', 'webhook'));
  END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS connectors_org_name_key
  ON public.connectors(org_id, name);

CREATE INDEX IF NOT EXISTS connectors_org_status_idx
  ON public.connectors(org_id, status);

DROP TRIGGER IF EXISTS connectors_set_updated_at ON public.connectors;
CREATE TRIGGER connectors_set_updated_at
  BEFORE UPDATE ON public.connectors
  FOR EACH ROW
  EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.connectors ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS connectors_org_scope ON public.connectors;
CREATE POLICY connectors_org_scope
  ON public.connectors
  FOR ALL
  USING (
    org_id IN (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
    )
  );
