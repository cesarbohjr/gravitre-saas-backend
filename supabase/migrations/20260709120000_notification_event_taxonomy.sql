-- Extend notification event taxonomy for unified emit_notification().

ALTER TABLE public.notifications DROP CONSTRAINT IF EXISTS notifications_type_check;

ALTER TABLE public.notifications
  ADD CONSTRAINT notifications_type_check
  CHECK (type IN (
    'approval_needed',
    'assignment_created',
    'assignment_changed',
    'run_completed',
    'run_failed',
    'run_started',
    'scheduled_run_completed',
    'scheduled_run_failed',
    'mention',
    'team_invite',
    'system',
    'agent_created',
    'workflow_created',
    'task_completed'
  ));
