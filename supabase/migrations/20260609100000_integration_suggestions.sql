-- STA-123: Auto-suggest connectors & workflows from audit data

CREATE TABLE IF NOT EXISTS public.integration_suggestions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  suggestion_type text NOT NULL,
  connector_type text,
  pack_id text,
  workflow_template_id text,
  title text NOT NULL,
  message text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  confidence numeric,
  priority integer NOT NULL DEFAULT 50,
  status text NOT NULL DEFAULT 'open',
  suggested_at timestamptz NOT NULL DEFAULT now(),
  dismissed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'integration_suggestions_type_check'
      AND conrelid = 'public.integration_suggestions'::regclass
  ) THEN
    ALTER TABLE public.integration_suggestions
      ADD CONSTRAINT integration_suggestions_type_check
      CHECK (suggestion_type IN (
        'connect_connector',
        'install_department_pack',
        'automate_workflow'
      ));
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'integration_suggestions_status_check'
      AND conrelid = 'public.integration_suggestions'::regclass
  ) THEN
    ALTER TABLE public.integration_suggestions
      ADD CONSTRAINT integration_suggestions_status_check
      CHECK (status IN ('open', 'dismissed', 'applied'));
  END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_integration_suggestions_org
  ON public.integration_suggestions (org_id, status, priority DESC, suggested_at DESC);

CREATE INDEX IF NOT EXISTS idx_integration_suggestions_connector
  ON public.integration_suggestions (org_id, connector_type, status);

ALTER TABLE public.integration_suggestions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "integration_suggestions_org_scope" ON public.integration_suggestions;
CREATE POLICY "integration_suggestions_org_scope"
  ON public.integration_suggestions FOR ALL
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

DROP TRIGGER IF EXISTS trg_integration_suggestions_updated_at ON public.integration_suggestions;
CREATE TRIGGER trg_integration_suggestions_updated_at
BEFORE UPDATE ON public.integration_suggestions
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.integration_suggestions IS
  'Audit-driven connector and workflow recommendations (STA-123).';
