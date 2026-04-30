-- GRAVITRE AI services tracking tables

CREATE TABLE IF NOT EXISTS model_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    task_type TEXT NOT NULL,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    latency_ms INTEGER,
    cost_usd NUMERIC(10,6),
    cache_hit BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    workflow_id UUID REFERENCES workflow_defs(id),
    run_id UUID,
    node_id TEXT,
    decision_type TEXT NOT NULL,
    selected_path TEXT NOT NULL,
    confidence NUMERIC(3,2),
    reasoning_summary TEXT,
    key_factors JSONB DEFAULT '[]',
    risks_identified JSONB DEFAULT '[]',
    alternatives_rejected JSONB DEFAULT '[]',
    requires_human_approval BOOLEAN DEFAULT false,
    rule_matches JSONB,
    ai_reasoning JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_councils (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    workflow_id UUID,
    run_id UUID,
    objective TEXT NOT NULL,
    options JSONB NOT NULL DEFAULT '[]',
    decision_method TEXT NOT NULL,
    participating_agents JSONB NOT NULL DEFAULT '[]',
    debate_rounds JSONB DEFAULT '[]',
    final_recommendation TEXT,
    final_confidence NUMERIC(3,2),
    dissenting_opinions JSONB DEFAULT '[]',
    status TEXT DEFAULT 'in_progress',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS optimization_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    workflow_id UUID NOT NULL REFERENCES workflow_defs(id),
    recommendation_type TEXT NOT NULL,
    title TEXT NOT NULL,
    issue TEXT NOT NULL,
    suggested_change TEXT NOT NULL,
    estimated_impact TEXT,
    confidence NUMERIC(3,2),
    risk TEXT DEFAULT 'low',
    status TEXT DEFAULT 'pending',
    applied_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_model_calls_org_date ON model_calls(org_id, created_at);
CREATE INDEX IF NOT EXISTS idx_decisions_run ON decisions(run_id);
CREATE INDEX IF NOT EXISTS idx_councils_org ON agent_councils(org_id);
CREATE INDEX IF NOT EXISTS idx_opt_recommendations_workflow ON optimization_recommendations(workflow_id);

ALTER TABLE model_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_councils ENABLE ROW LEVEL SECURITY;
ALTER TABLE optimization_recommendations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Org members can read model calls" ON model_calls;
CREATE POLICY "Org members can read model calls"
  ON model_calls
  FOR SELECT
  USING (
    org_id IN (
      SELECT om.org_id
      FROM organization_members om
      WHERE om.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "Org admins can manage model calls" ON model_calls;
CREATE POLICY "Org admins can manage model calls"
  ON model_calls
  FOR ALL
  USING (
    org_id IN (
      SELECT om.org_id
      FROM organization_members om
      WHERE om.user_id = auth.uid()
      AND om.role IN ('owner', 'admin')
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT om.org_id
      FROM organization_members om
      WHERE om.user_id = auth.uid()
      AND om.role IN ('owner', 'admin')
    )
  );

DROP POLICY IF EXISTS "Org members can read decisions" ON decisions;
CREATE POLICY "Org members can read decisions"
  ON decisions
  FOR SELECT
  USING (
    org_id IN (
      SELECT om.org_id
      FROM organization_members om
      WHERE om.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "Org admins can manage decisions" ON decisions;
CREATE POLICY "Org admins can manage decisions"
  ON decisions
  FOR ALL
  USING (
    org_id IN (
      SELECT om.org_id
      FROM organization_members om
      WHERE om.user_id = auth.uid()
      AND om.role IN ('owner', 'admin')
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT om.org_id
      FROM organization_members om
      WHERE om.user_id = auth.uid()
      AND om.role IN ('owner', 'admin')
    )
  );

DROP POLICY IF EXISTS "Org members can read councils" ON agent_councils;
CREATE POLICY "Org members can read councils"
  ON agent_councils
  FOR SELECT
  USING (
    org_id IN (
      SELECT om.org_id
      FROM organization_members om
      WHERE om.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "Org admins can manage councils" ON agent_councils;
CREATE POLICY "Org admins can manage councils"
  ON agent_councils
  FOR ALL
  USING (
    org_id IN (
      SELECT om.org_id
      FROM organization_members om
      WHERE om.user_id = auth.uid()
      AND om.role IN ('owner', 'admin')
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT om.org_id
      FROM organization_members om
      WHERE om.user_id = auth.uid()
      AND om.role IN ('owner', 'admin')
    )
  );

DROP POLICY IF EXISTS "Org members can read optimization recs" ON optimization_recommendations;
CREATE POLICY "Org members can read optimization recs"
  ON optimization_recommendations
  FOR SELECT
  USING (
    org_id IN (
      SELECT om.org_id
      FROM organization_members om
      WHERE om.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "Org admins can manage optimization recs" ON optimization_recommendations;
CREATE POLICY "Org admins can manage optimization recs"
  ON optimization_recommendations
  FOR ALL
  USING (
    org_id IN (
      SELECT om.org_id
      FROM organization_members om
      WHERE om.user_id = auth.uid()
      AND om.role IN ('owner', 'admin')
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT om.org_id
      FROM organization_members om
      WHERE om.user_id = auth.uid()
      AND om.role IN ('owner', 'admin')
    )
  );
