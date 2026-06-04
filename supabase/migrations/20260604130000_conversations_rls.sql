-- Conversations: user-private rows within org + RLS for direct Supabase Data API access.
-- user_id stores auth.users.id (JWT sub), matching organization_members.user_id.

ALTER TABLE public.conversations
  DROP CONSTRAINT IF EXISTS conversations_user_id_fkey;

ALTER TABLE public.conversations
  ADD CONSTRAINT conversations_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversation_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "conversations_select_own" ON public.conversations;
CREATE POLICY "conversations_select_own"
  ON public.conversations FOR SELECT
  USING (
    user_id = auth.uid()
    AND org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "conversations_insert_own" ON public.conversations;
CREATE POLICY "conversations_insert_own"
  ON public.conversations FOR INSERT
  WITH CHECK (
    user_id = auth.uid()
    AND org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "conversations_update_own" ON public.conversations;
CREATE POLICY "conversations_update_own"
  ON public.conversations FOR UPDATE
  USING (
    user_id = auth.uid()
    AND org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    user_id = auth.uid()
    AND org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "conversations_delete_own" ON public.conversations;
CREATE POLICY "conversations_delete_own"
  ON public.conversations FOR DELETE
  USING (
    user_id = auth.uid()
    AND org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "conversation_messages_select_own" ON public.conversation_messages;
CREATE POLICY "conversation_messages_select_own"
  ON public.conversation_messages FOR SELECT
  USING (
    EXISTS (
      SELECT 1
      FROM public.conversations c
      WHERE c.id = conversation_id
        AND c.user_id = auth.uid()
        AND c.org_id IN (
          SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
        )
    )
  );

DROP POLICY IF EXISTS "conversation_messages_insert_own" ON public.conversation_messages;
CREATE POLICY "conversation_messages_insert_own"
  ON public.conversation_messages FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM public.conversations c
      WHERE c.id = conversation_id
        AND c.user_id = auth.uid()
        AND c.org_id IN (
          SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
        )
    )
  );

DROP POLICY IF EXISTS "conversation_messages_update_own" ON public.conversation_messages;
CREATE POLICY "conversation_messages_update_own"
  ON public.conversation_messages FOR UPDATE
  USING (
    EXISTS (
      SELECT 1
      FROM public.conversations c
      WHERE c.id = conversation_id
        AND c.user_id = auth.uid()
        AND c.org_id IN (
          SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
        )
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM public.conversations c
      WHERE c.id = conversation_id
        AND c.user_id = auth.uid()
        AND c.org_id IN (
          SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
        )
    )
  );

DROP POLICY IF EXISTS "conversation_messages_delete_own" ON public.conversation_messages;
CREATE POLICY "conversation_messages_delete_own"
  ON public.conversation_messages FOR DELETE
  USING (
    EXISTS (
      SELECT 1
      FROM public.conversations c
      WHERE c.id = conversation_id
        AND c.user_id = auth.uid()
        AND c.org_id IN (
          SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
        )
    )
  );
