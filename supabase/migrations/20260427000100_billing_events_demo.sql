-- Demo-safe persistent billing action log for v0 billing page.
-- Compatibility note:
-- - Older migrations created public.billing_events(event_type, payload, created_at)
-- - New API expects public.billing_events(action, status, payload, created_at, updated_at)
-- This migration reconciles both shapes idempotently.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TABLE IF NOT EXISTS public.billing_events (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  action text,
  event_type text,
  status text NOT NULL DEFAULT 'success',
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.billing_events
  ADD COLUMN IF NOT EXISTS action text,
  ADD COLUMN IF NOT EXISTS event_type text,
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'success',
  ADD COLUMN IF NOT EXISTS payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'billing_events'
      AND column_name = 'event_type'
  ) THEN
    UPDATE public.billing_events
    SET action = COALESCE(action, event_type, 'unknown')
    WHERE action IS NULL;
  ELSE
    UPDATE public.billing_events
    SET action = COALESCE(action, 'unknown')
    WHERE action IS NULL;
  END IF;
END;
$$;

ALTER TABLE public.billing_events
  ALTER COLUMN action SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'billing_events_status_check'
      AND conrelid = 'public.billing_events'::regclass
  ) THEN
    ALTER TABLE public.billing_events
      ADD CONSTRAINT billing_events_status_check
      CHECK (status IN ('success', 'pending', 'failed'));
  END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_billing_events_org_id
  ON public.billing_events(org_id);
CREATE INDEX IF NOT EXISTS idx_billing_events_created_at
  ON public.billing_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_billing_events_action
  ON public.billing_events(action);

ALTER TABLE public.billing_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "billing_events_org_scope" ON public.billing_events;
CREATE POLICY "billing_events_org_scope"
  ON public.billing_events FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

DROP TRIGGER IF EXISTS trg_billing_events_updated_at ON public.billing_events;
CREATE TRIGGER trg_billing_events_updated_at
BEFORE UPDATE ON public.billing_events
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
