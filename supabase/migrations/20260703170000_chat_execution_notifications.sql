-- Extend notification types for conversational operator completions.

ALTER TABLE public.notifications DROP CONSTRAINT IF EXISTS notifications_type_check;

ALTER TABLE public.notifications
  ADD CONSTRAINT notifications_type_check
  CHECK (type IN (
    'approval_needed',
    'assignment_created',
    'run_completed',
    'run_failed',
    'mention',
    'team_invite',
    'system',
    'agent_created',
    'workflow_created',
    'task_completed'
  ));
