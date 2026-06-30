-- Extended Intelligence Engine: v4 memory taxonomy, v6 business entity types (documented),
-- v10 proactive signal support, static org process inventory (v9 bounded scope)

-- v4: extend memory category taxonomy (no new tables)
ALTER TABLE public.agent_memories
  DROP CONSTRAINT IF EXISTS agent_memories_category_check;

ALTER TABLE public.agent_memories
  ADD CONSTRAINT agent_memories_category_check
  CHECK (category IN (
    'fact', 'preference', 'pattern', 'rule',
    'campaign_learning', 'risk_signal', 'business_rule'
  ));

ALTER TABLE public.memory_promotion_candidates
  DROP CONSTRAINT IF EXISTS memory_promotion_candidates_memory_category_check;

ALTER TABLE public.memory_promotion_candidates
  ADD CONSTRAINT memory_promotion_candidates_memory_category_check
  CHECK (memory_category IN (
    'fact', 'preference', 'pattern', 'rule',
    'campaign_learning', 'risk_signal', 'business_rule'
  ));

COMMENT ON TABLE public.org_entity_relationships IS
  'v6 soft relationship layer; one-hop traversal only. Entity types include internal '
  '(glossary_term, department, agent, query_cluster) and connector-sourced business '
  '(customer, lead, deal, campaign, support_ticket, invoice, project, employee, vendor).';

-- v9 bounded: admin-entered process inventory — NOT a simulation engine
CREATE TABLE IF NOT EXISTS public.organization_process_inventory (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  department text NOT NULL,
  process_name text NOT NULL,
  process_owner text,
  frequency text,
  manual_effort_hours_estimate numeric,
  admin_entered_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_organization_process_inventory_org
  ON public.organization_process_inventory (org_id, department);

ALTER TABLE public.organization_process_inventory ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS organization_process_inventory_org ON public.organization_process_inventory;
CREATE POLICY organization_process_inventory_org
  ON public.organization_process_inventory FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

COMMENT ON TABLE public.organization_process_inventory IS
  'Admin-entered reference inventory for v10 detectors; not predictive simulation.';
