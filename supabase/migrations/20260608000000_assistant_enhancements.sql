-- Assistant enhancements: conversation lifecycle + user intelligence

ALTER TABLE public.conversations
  ADD COLUMN IF NOT EXISTS archived_at timestamptz,
  ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_conversations_org_user_active
  ON public.conversations (org_id, user_id, updated_at DESC)
  WHERE deleted_at IS NULL AND archived_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_conversations_title_search
  ON public.conversations USING gin (to_tsvector('english', coalesce(title, '')));

CREATE TABLE IF NOT EXISTS public.user_query_patterns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  query_text text NOT NULL,
  query_category text,
  response_quality double precision,
  model_used text,
  response_time_ms integer,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.user_preferences (
  user_id uuid PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  preferred_model text,
  preferred_mode text DEFAULT 'standard',
  personalized_suggestions jsonb DEFAULT '[]'::jsonb,
  last_session_at timestamptz,
  query_categories jsonb DEFAULT '{}'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.user_query_patterns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "user_isolation_patterns"
  ON public.user_query_patterns FOR ALL
  USING (user_id = auth.uid());

CREATE POLICY "user_isolation_preferences"
  ON public.user_preferences FOR ALL
  USING (user_id = auth.uid());

CREATE INDEX IF NOT EXISTS idx_user_query_patterns_user_category
  ON public.user_query_patterns (user_id, query_category, created_at DESC);
