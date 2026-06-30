-- STA-293: Mode B feedback infrastructure (guardrails, toggle, post-hoc audit)

CREATE TABLE IF NOT EXISTS public.org_feedback_settings (
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  pack_slug text NOT NULL DEFAULT '',
  feedback_mode text NOT NULL DEFAULT 'mode_a'
    CHECK (feedback_mode IN ('mode_a', 'mode_b')),
  max_shift_percent_per_cycle numeric NOT NULL DEFAULT 15
    CHECK (max_shift_percent_per_cycle > 0 AND max_shift_percent_per_cycle <= 100),
  cycle_shift_total numeric NOT NULL DEFAULT 0
    CHECK (cycle_shift_total >= 0),
  cycle_started_at timestamptz NOT NULL DEFAULT now(),
  mode_b_risk_acknowledged_at timestamptz,
  mode_b_risk_acknowledged_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, pack_slug)
);

CREATE INDEX IF NOT EXISTS idx_org_feedback_settings_org
  ON public.org_feedback_settings (org_id);

CREATE TABLE IF NOT EXISTS public.mode_b_autonomous_mutations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  agent_id uuid NOT NULL REFERENCES public.agents(id) ON DELETE CASCADE,
  pack_slug text NOT NULL DEFAULT '',
  dimension text NOT NULL
    CHECK (dimension IN ('tone', 'cadence', 'content_type')),
  before_value text NOT NULL,
  after_value text NOT NULL,
  shift_percent numeric NOT NULL DEFAULT 0
    CHECK (shift_percent >= 0),
  mutation_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  agent_config_before jsonb NOT NULL DEFAULT '{}'::jsonb,
  agent_config_after jsonb NOT NULL DEFAULT '{}'::jsonb,
  outcome_win_rate_before numeric,
  outcome_win_rate_after numeric,
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'rolled_back')),
  rolled_back_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mode_b_mutations_org_agent
  ON public.mode_b_autonomous_mutations (org_id, agent_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.mode_b_autonomous_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  mutation_id uuid REFERENCES public.mode_b_autonomous_mutations(id) ON DELETE SET NULL,
  event_type text NOT NULL
    CHECK (event_type IN (
      'mutation_applied',
      'rollback',
      'cap_blocked',
      'replan_cycle',
      'mode_enabled',
      'mode_disabled'
    )),
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mode_b_events_org
  ON public.mode_b_autonomous_events (org_id, created_at DESC);

ALTER TABLE public.org_feedback_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mode_b_autonomous_mutations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mode_b_autonomous_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "org_feedback_settings_org" ON public.org_feedback_settings;
CREATE POLICY "org_feedback_settings_org"
  ON public.org_feedback_settings FOR ALL
  USING (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()))
  WITH CHECK (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()));

DROP POLICY IF EXISTS "mode_b_mutations_org" ON public.mode_b_autonomous_mutations;
CREATE POLICY "mode_b_mutations_org"
  ON public.mode_b_autonomous_mutations FOR ALL
  USING (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()))
  WITH CHECK (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()));

DROP POLICY IF EXISTS "mode_b_events_org" ON public.mode_b_autonomous_events;
CREATE POLICY "mode_b_events_org"
  ON public.mode_b_autonomous_events FOR ALL
  USING (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()))
  WITH CHECK (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()));

DROP TRIGGER IF EXISTS org_feedback_settings_updated_at ON public.org_feedback_settings;
CREATE TRIGGER org_feedback_settings_updated_at
BEFORE UPDATE ON public.org_feedback_settings
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.org_feedback_settings IS
  'Org/pack feedback mode toggle (Mode A default, Mode B opt-in with risk gate).';

COMMENT ON TABLE public.mode_b_autonomous_mutations IS
  'Autonomous behavior mutations with config snapshots for rollback (STA-293).';

COMMENT ON TABLE public.mode_b_autonomous_events IS
  'Post-hoc audit trail for Mode B actions without human approval anchor.';
