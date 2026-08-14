-- CognitiveTurnKernel Phase 1+: traces, memory taxonomy, metrics SoT, field ACL, org knowledge nodes.

-- ---------------------------------------------------------------------------
-- cognitive_turn_traces — per-turn stage timeline (org-scoped)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.cognitive_turn_traces (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id uuid,
  conversation_id uuid,
  turn_id uuid NOT NULL,
  surface text,
  stages jsonb NOT NULL DEFAULT '[]'::jsonb,
  memory_summary jsonb,
  knowledge_summary jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cognitive_turn_traces_org_id
  ON public.cognitive_turn_traces (org_id);

CREATE INDEX IF NOT EXISTS idx_cognitive_turn_traces_org_turn
  ON public.cognitive_turn_traces (org_id, turn_id);

CREATE INDEX IF NOT EXISTS idx_cognitive_turn_traces_org_created
  ON public.cognitive_turn_traces (org_id, created_at DESC);

ALTER TABLE public.cognitive_turn_traces ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "cognitive_turn_traces_org_scope" ON public.cognitive_turn_traces;
CREATE POLICY "cognitive_turn_traces_org_scope"
  ON public.cognitive_turn_traces FOR ALL
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

-- ---------------------------------------------------------------------------
-- Expand agent_memories category check (keep prior values + cognitive taxonomy)
-- ---------------------------------------------------------------------------
ALTER TABLE public.agent_memories
  DROP CONSTRAINT IF EXISTS agent_memories_category_check;

ALTER TABLE public.agent_memories
  ADD CONSTRAINT agent_memories_category_check
  CHECK (category IN (
    'fact', 'preference', 'pattern', 'rule',
    'campaign_learning', 'risk_signal', 'business_rule',
    'working', 'episodic', 'decision', 'outcome', 'relationship', 'procedural'
  ));

ALTER TABLE public.memory_promotion_candidates
  DROP CONSTRAINT IF EXISTS memory_promotion_candidates_memory_category_check;

ALTER TABLE public.memory_promotion_candidates
  ADD CONSTRAINT memory_promotion_candidates_memory_category_check
  CHECK (memory_category IN (
    'fact', 'preference', 'pattern', 'rule',
    'campaign_learning', 'risk_signal', 'business_rule',
    'working', 'episodic', 'decision', 'outcome', 'relationship', 'procedural'
  ));

-- ---------------------------------------------------------------------------
-- org_metric_definitions — authoritative per-org KPI semantic layer
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.org_metric_definitions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  metric_key text NOT NULL,
  label text,
  formula text,
  source_system text,
  owner text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, metric_key)
);

CREATE INDEX IF NOT EXISTS idx_org_metric_definitions_org_id
  ON public.org_metric_definitions (org_id);

ALTER TABLE public.org_metric_definitions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "org_metric_definitions_org_scope" ON public.org_metric_definitions;
CREATE POLICY "org_metric_definitions_org_scope"
  ON public.org_metric_definitions FOR ALL
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

-- ---------------------------------------------------------------------------
-- org_field_permissions — field-level allow/deny for agent reads
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.org_field_permissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  role text NOT NULL,
  resource text NOT NULL,
  field_key text NOT NULL,
  effect text NOT NULL CHECK (effect IN ('allow', 'deny')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_org_field_permissions_org_id
  ON public.org_field_permissions (org_id);

CREATE INDEX IF NOT EXISTS idx_org_field_permissions_lookup
  ON public.org_field_permissions (org_id, role, resource, field_key);

ALTER TABLE public.org_field_permissions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "org_field_permissions_org_scope" ON public.org_field_permissions;
CREATE POLICY "org_field_permissions_org_scope"
  ON public.org_field_permissions FOR ALL
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

-- ---------------------------------------------------------------------------
-- org_knowledge_nodes — typed org graph nodes (company, employee, …)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.org_knowledge_nodes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  node_type text NOT NULL CHECK (node_type IN (
    'company', 'employee', 'customer', 'prospect', 'vendor', 'product',
    'competitor', 'project', 'campaign', 'contract', 'kpi', 'system', 'decision'
  )),
  name text NOT NULL,
  attributes jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_org_knowledge_nodes_org_id
  ON public.org_knowledge_nodes (org_id);

CREATE INDEX IF NOT EXISTS idx_org_knowledge_nodes_org_type
  ON public.org_knowledge_nodes (org_id, node_type);

ALTER TABLE public.org_knowledge_nodes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "org_knowledge_nodes_org_scope" ON public.org_knowledge_nodes;
CREATE POLICY "org_knowledge_nodes_org_scope"
  ON public.org_knowledge_nodes FOR ALL
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

COMMENT ON TABLE public.org_knowledge_nodes IS
  'CognitiveTurnKernel org knowledge graph nodes. Complements org_entity_relationships '
  'edges; node_type taxonomy covers company/employee/customer/prospect/vendor/product/'
  'competitor/project/campaign/contract/kpi/system/decision.';

COMMENT ON TABLE public.org_entity_relationships IS
  'v6 soft relationship layer; one-hop traversal only. Entity types include internal '
  '(glossary_term, department, agent, query_cluster) and connector-sourced business '
  '(customer, lead, deal, campaign, support_ticket, invoice, project, employee, vendor). '
  'CognitiveTurnKernel may also reference org_knowledge_nodes for typed org graph nodes.';
