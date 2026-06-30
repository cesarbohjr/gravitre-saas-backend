-- STA-290: Batch + partial approval for in-graph approval gates

CREATE TABLE IF NOT EXISTS public.approval_batches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  run_id uuid NOT NULL REFERENCES public.workflow_runs(id) ON DELETE CASCADE,
  node_id text NOT NULL,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'partial', 'resolved')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_approval_batches_run
  ON public.approval_batches (run_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_approval_batches_org
  ON public.approval_batches (org_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.approval_batch_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id uuid NOT NULL REFERENCES public.approval_batches(id) ON DELETE CASCADE,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  item_key text NOT NULL,
  label text NOT NULL,
  source_node_id text,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'approved', 'rejected')),
  reject_comment text,
  route_to_node_id text,
  decided_at timestamptz,
  decided_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (batch_id, item_key)
);

CREATE INDEX IF NOT EXISTS idx_approval_batch_items_batch
  ON public.approval_batch_items (batch_id, status);

ALTER TABLE public.approval_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.approval_batch_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "approval_batches_org" ON public.approval_batches;
CREATE POLICY "approval_batches_org"
  ON public.approval_batches FOR ALL
  USING (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()))
  WITH CHECK (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()));

DROP POLICY IF EXISTS "approval_batch_items_org" ON public.approval_batch_items;
CREATE POLICY "approval_batch_items_org"
  ON public.approval_batch_items FOR ALL
  USING (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()))
  WITH CHECK (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()));

DROP TRIGGER IF EXISTS approval_batches_updated_at ON public.approval_batches;
CREATE TRIGGER approval_batches_updated_at
BEFORE UPDATE ON public.approval_batches
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS approval_batch_items_updated_at ON public.approval_batch_items;
CREATE TRIGGER approval_batch_items_updated_at
BEFORE UPDATE ON public.approval_batch_items
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.approval_batches IS
  'Grouped approval gate over multiple upstream deliverables (STA-290 / MKT-PACK 5.2).';

COMMENT ON TABLE public.approval_batch_items IS
  'Per-item approve/reject within an approval batch with optional upstream re-entry routing.';
