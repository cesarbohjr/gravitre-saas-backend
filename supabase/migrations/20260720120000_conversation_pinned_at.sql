-- Persist pin state for chat history (pinned threads stay above recency buckets).
ALTER TABLE public.conversations
  ADD COLUMN IF NOT EXISTS pinned_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_conversations_org_user_pinned_updated
  ON public.conversations (org_id, user_id, pinned_at DESC NULLS LAST, updated_at DESC)
  WHERE deleted_at IS NULL AND archived_at IS NULL;
