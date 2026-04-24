-- Phase 14: Workflow orchestration nodes + edges
-- Authority: WF-ORCH-01

CREATE TABLE public.workflow_nodes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  workflow_id uuid NOT NULL REFERENCES public.workflow_defs(id) ON DELETE CASCADE,
  environment text NOT NULL,
  node_type text NOT NULL CHECK (node_type IN ('agent', 'task', 'connector', 'tool', 'source')),
  title text NOT NULL,
  instruction text,
  operator_id uuid REFERENCES public.operators(id) ON DELETE SET NULL,
  connector_id uuid REFERENCES public.connectors(id) ON DELETE SET NULL,
  source_id uuid REFERENCES public.rag_sources(id) ON DELETE SET NULL,
  tool_type text,
  tool_config jsonb,
  position jsonb,
  metadata jsonb,
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  updated_by uuid REFERENCES auth.users(id) ON DELETE SET NULL
);

CREATE INDEX idx_workflow_nodes_org_id ON public.workflow_nodes(org_id);
CREATE INDEX idx_workflow_nodes_workflow_id ON public.workflow_nodes(workflow_id);
CREATE INDEX idx_workflow_nodes_environment ON public.workflow_nodes(environment);
CREATE INDEX idx_workflow_nodes_type ON public.workflow_nodes(node_type);

CREATE TABLE public.workflow_edges (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  workflow_id uuid NOT NULL REFERENCES public.workflow_defs(id) ON DELETE CASCADE,
  environment text NOT NULL,
  from_node_id uuid NOT NULL REFERENCES public.workflow_nodes(id) ON DELETE CASCADE,
  to_node_id uuid NOT NULL REFERENCES public.workflow_nodes(id) ON DELETE CASCADE,
  edge_type text NOT NULL CHECK (edge_type IN ('sequence', 'branch', 'condition')),
  condition jsonb,
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_workflow_edges_org_id ON public.workflow_edges(org_id);
CREATE INDEX idx_workflow_edges_workflow_id ON public.workflow_edges(workflow_id);
CREATE INDEX idx_workflow_edges_from_node ON public.workflow_edges(from_node_id);
CREATE INDEX idx_workflow_edges_to_node ON public.workflow_edges(to_node_id);

ALTER TABLE public.workflow_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflow_edges ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workflow_nodes_org"
  ON public.workflow_nodes FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "workflow_edges_org"
  ON public.workflow_edges FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));
