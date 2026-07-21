-- Durable Save Question bookmarks for /ai chat (org + user scoped).

CREATE TABLE IF NOT EXISTS public.saved_questions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  conversation_id uuid REFERENCES public.conversations(id) ON DELETE SET NULL,
  message_id text,
  question_text text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS saved_questions_unique_message
  ON public.saved_questions (org_id, user_id, message_id)
  WHERE message_id IS NOT NULL AND length(trim(message_id)) > 0;

CREATE INDEX IF NOT EXISTS idx_saved_questions_user_created
  ON public.saved_questions (org_id, user_id, created_at DESC);

ALTER TABLE public.saved_questions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "saved_questions_org_user_scope" ON public.saved_questions;
CREATE POLICY "saved_questions_org_user_scope"
  ON public.saved_questions FOR ALL
  USING (
    user_id = auth.uid()
    AND org_id IN (
      SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()
    )
  )
  WITH CHECK (
    user_id = auth.uid()
    AND org_id IN (
      SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.saved_questions IS
  'User-saved chat questions from /ai (presentation Save Question action).';
