-- STA-146: Persist rolling conversation summary for long assistant threads

ALTER TABLE public.conversations
  ADD COLUMN IF NOT EXISTS last_summary text;
