-- Atomic claim of a governed pending WRITE on conversations.task_state.
-- Compare-and-set on pending_task.status; tenant-scoped; optional actor bind.

CREATE OR REPLACE FUNCTION public.claim_pending_connector_write(
  p_conversation_id uuid,
  p_org_id uuid,
  p_actor_id text,
  p_expected_status text,
  p_claim_id text,
  p_claimed_at text
)
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
  v_state jsonb;
BEGIN
  UPDATE public.conversations
     SET task_state = jsonb_set(
           jsonb_set(
             jsonb_set(
               COALESCE(task_state, '{}'::jsonb),
               '{pending_task,status}',
               to_jsonb('executing'::text),
               true
             ),
             '{pending_task,execution_claim_id}',
             to_jsonb(p_claim_id),
             true
           ),
           '{pending_task,claimed_at}',
           to_jsonb(p_claimed_at),
           true
         ),
         updated_at = now()
   WHERE id = p_conversation_id
     AND org_id = p_org_id
     AND COALESCE(task_state #>> '{pending_task,status}', '') = p_expected_status
     AND (
       COALESCE(task_state #>> '{pending_task,actor_id}', '') = ''
       OR COALESCE(p_actor_id, '') = ''
       OR task_state #>> '{pending_task,actor_id}' = p_actor_id
     )
  RETURNING task_state INTO v_state;

  RETURN v_state;
END;
$$;

REVOKE ALL ON FUNCTION public.claim_pending_connector_write(uuid, uuid, text, text, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.claim_pending_connector_write(uuid, uuid, text, text, text, text) TO service_role;
