-- Module 0 DB guard: restricted test credentials may only INSERT into
-- allow-listed isolated test orgs. Service-role bypasses RLS, so this is a
-- BEFORE INSERT trigger (not an RLS policy).
--
-- Actor columns:
--   conversations.user_id
--   audit_events.actor_id
--   workflow_runs.triggered_by
--   notifications.user_id  (recipient; blocks smoke-SA inbox pollution)

CREATE TABLE IF NOT EXISTS public.restricted_test_user_ids (
  user_id uuid PRIMARY KEY,
  note text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.test_credential_org_allowlist (
  org_id uuid PRIMARY KEY REFERENCES public.organizations(id) ON DELETE CASCADE,
  note text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO public.restricted_test_user_ids (user_id, note)
VALUES (
  'a9f1240f-910a-42ca-aebf-38caeac288c3',
  'conversation-smoke-sa@gravitre.app (prod Module 0 SA)'
)
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO public.test_credential_org_allowlist (org_id, note)
VALUES (
  'f07e57c0-1501-4000-8000-c04e57a00001',
  'gravitre-isolated-conversation-smoke'
)
ON CONFLICT (org_id) DO NOTHING;

CREATE OR REPLACE FUNCTION public.is_restricted_test_credential_actor(p_actor uuid)
RETURNS boolean
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  email text;
BEGIN
  IF p_actor IS NULL THEN
    RETURN false;
  END IF;

  IF EXISTS (
    SELECT 1 FROM public.restricted_test_user_ids r WHERE r.user_id = p_actor
  ) THEN
    RETURN true;
  END IF;

  BEGIN
    SELECT lower(u.email) INTO email
    FROM auth.users u
    WHERE u.id = p_actor;
  EXCEPTION
    WHEN undefined_table THEN
      email := NULL;
    WHEN insufficient_privilege THEN
      email := NULL;
  END;

  IF email IS NULL OR email = '' THEN
    RETURN false;
  END IF;

  -- Mirror backend conversation_write_guard._SMOKE_EMAIL_RE
  IF email ~ '^(conversation-smoke-sa@)'
     OR email ~ '^(ci\+)'
     OR email ~ '^(smoke[-+.])'
     OR email ~ '([-+. ]smoke@)'
     OR email ~ '(@.*\.smoke\.gravitre\.app)$'
  THEN
    RETURN true;
  END IF;

  RETURN false;
END;
$$;

CREATE OR REPLACE FUNCTION public.is_isolated_test_org(p_org_id uuid)
RETURNS boolean
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF p_org_id IS NULL THEN
    RETURN false;
  END IF;

  IF EXISTS (
    SELECT 1 FROM public.test_credential_org_allowlist a WHERE a.org_id = p_org_id
  ) THEN
    RETURN true;
  END IF;

  RETURN EXISTS (
    SELECT 1
    FROM public.organizations o
    WHERE o.id = p_org_id
      AND COALESCE((o.settings->>'isolated_conversation_test_org')::boolean, false) = true
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.enforce_test_credential_isolated_org()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  actor uuid;
BEGIN
  -- Emergency ops escape hatch (session-local):
  --   SET LOCAL gravitree.bypass_test_credential_org_guard = 'on';
  IF current_setting('gravitree.bypass_test_credential_org_guard', true) = 'on' THEN
    RETURN NEW;
  END IF;

  IF TG_TABLE_NAME = 'conversations' THEN
    actor := NEW.user_id;
  ELSIF TG_TABLE_NAME = 'audit_events' THEN
    actor := NEW.actor_id;
  ELSIF TG_TABLE_NAME = 'workflow_runs' THEN
    actor := NEW.triggered_by;
  ELSIF TG_TABLE_NAME = 'notifications' THEN
    actor := NEW.user_id;
  ELSE
    RETURN NEW;
  END IF;

  IF NOT public.is_restricted_test_credential_actor(actor) THEN
    RETURN NEW;
  END IF;

  IF public.is_isolated_test_org(NEW.org_id) THEN
    RETURN NEW;
  END IF;

  RAISE EXCEPTION
    'REFUSING % insert: test/service credential % cannot write into org % (isolated test org only)',
    TG_TABLE_NAME,
    actor,
    NEW.org_id
    USING ERRCODE = 'check_violation';
END;
$$;

DROP TRIGGER IF EXISTS trg_conversations_test_credential_org_guard ON public.conversations;
CREATE TRIGGER trg_conversations_test_credential_org_guard
  BEFORE INSERT ON public.conversations
  FOR EACH ROW
  EXECUTE FUNCTION public.enforce_test_credential_isolated_org();

DROP TRIGGER IF EXISTS trg_audit_events_test_credential_org_guard ON public.audit_events;
CREATE TRIGGER trg_audit_events_test_credential_org_guard
  BEFORE INSERT ON public.audit_events
  FOR EACH ROW
  EXECUTE FUNCTION public.enforce_test_credential_isolated_org();

DROP TRIGGER IF EXISTS trg_workflow_runs_test_credential_org_guard ON public.workflow_runs;
CREATE TRIGGER trg_workflow_runs_test_credential_org_guard
  BEFORE INSERT ON public.workflow_runs
  FOR EACH ROW
  EXECUTE FUNCTION public.enforce_test_credential_isolated_org();

DROP TRIGGER IF EXISTS trg_notifications_test_credential_org_guard ON public.notifications;
CREATE TRIGGER trg_notifications_test_credential_org_guard
  BEFORE INSERT ON public.notifications
  FOR EACH ROW
  EXECUTE FUNCTION public.enforce_test_credential_isolated_org();

COMMENT ON FUNCTION public.enforce_test_credential_isolated_org() IS
  'Module 0: block restricted test credentials from inserting into non-isolated orgs (service-role safe).';
