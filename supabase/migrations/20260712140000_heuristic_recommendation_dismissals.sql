-- STA-314: per-user dismissals for heuristic recommendation cards (STA-123 pattern).
CREATE TABLE IF NOT EXISTS public.heuristic_recommendation_dismissals (
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  card_id text NOT NULL,
  dismissed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, user_id, card_id)
);

CREATE INDEX IF NOT EXISTS idx_heuristic_recommendation_dismissals_user
  ON public.heuristic_recommendation_dismissals (org_id, user_id, dismissed_at DESC);

ALTER TABLE public.heuristic_recommendation_dismissals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "heuristic_recommendation_dismissals_org_scope"
  ON public.heuristic_recommendation_dismissals;
CREATE POLICY "heuristic_recommendation_dismissals_org_scope"
  ON public.heuristic_recommendation_dismissals FOR ALL
  USING (
    org_id IN (
      SELECT organization_members.org_id
      FROM public.organization_members
      WHERE organization_members.user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT organization_members.org_id
      FROM public.organization_members
      WHERE organization_members.user_id = auth.uid()
    )
    AND user_id = auth.uid()
  );

COMMENT ON TABLE public.heuristic_recommendation_dismissals IS
  'STA-314 per-user dismissals for suggest-only heuristic cards; never triggers tool execution.';
