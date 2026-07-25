-- Seed a production environment for orgs that never got one, and make sure
-- signup creates production going forward. Subscription purchasers stay org owners.

INSERT INTO public.environments (org_id, name, is_active)
SELECT o.id, 'production', true
FROM public.organizations o
WHERE NOT EXISTS (
  SELECT 1 FROM public.environments e WHERE e.org_id = o.id
)
ON CONFLICT DO NOTHING;

-- Billing-active / trialing org creators who are still "admin" become owner.
UPDATE public.organization_members AS om
SET role = 'owner'
FROM public.org_billing ob
WHERE om.org_id = ob.org_id
  AND om.role = 'admin'
  AND COALESCE(ob.billing_status, '') IN ('active', 'trialing')
  AND om.id IN (
    SELECT DISTINCT ON (org_id) id
    FROM public.organization_members
    ORDER BY org_id, created_at ASC NULLS LAST, id ASC
  );

UPDATE public.users AS u
SET role = 'owner'
FROM public.organization_members om
WHERE u.auth_user_id = om.user_id
  AND u.org_id = om.org_id
  AND om.role = 'owner'
  AND COALESCE(u.role, '') <> 'owner';

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_org_id uuid;
  v_org_name text;
  v_slug text;
  v_email text;
  v_full_name text;
  v_trial_end timestamptz;
BEGIN
  IF EXISTS (
    SELECT 1 FROM public.organization_members om WHERE om.user_id = NEW.id
  ) THEN
    RETURN NEW;
  END IF;

  v_email := COALESCE(NEW.email, '');
  v_full_name := COALESCE(
    NEW.raw_user_meta_data->>'full_name',
    NEW.raw_user_meta_data->>'name',
    split_part(v_email, '@', 1),
    'User'
  );
  v_org_name := COALESCE(
    NULLIF(trim(NEW.raw_user_meta_data->>'company_name'), ''),
    v_full_name || '''s Workspace',
    'My Workspace'
  );
  v_slug := lower(regexp_replace(v_org_name, '[^a-zA-Z0-9]+', '-', 'g'));
  v_slug := trim(both '-' from v_slug);
  IF v_slug = '' OR v_slug IS NULL THEN
    v_slug := 'workspace';
  END IF;
  v_slug := v_slug || '-' || substr(replace(NEW.id::text, '-', ''), 1, 8);
  v_trial_end := now() + interval '7 days';

  INSERT INTO public.organizations (name, slug, status, settings)
  VALUES (
    v_org_name,
    v_slug,
    'active',
    jsonb_build_object(
      'onboarding', jsonb_build_object(
        'seeded', false,
        'checklist_dismissed', false,
        'completed_steps', '[]'::jsonb
      ),
      'billing', jsonb_build_object(
        'trial_started_at', now(),
        'trial_ends_at', v_trial_end
      )
    )
  )
  RETURNING id INTO v_org_id;

  INSERT INTO public.organization_members (org_id, user_id, role)
  VALUES (v_org_id, NEW.id, 'owner');

  INSERT INTO public.users (org_id, auth_user_id, email, full_name, role, status)
  VALUES (v_org_id, NEW.id, v_email, v_full_name, 'owner', 'active')
  ON CONFLICT (auth_user_id) DO UPDATE SET
    org_id = EXCLUDED.org_id,
    email = EXCLUDED.email,
    full_name = COALESCE(public.users.full_name, EXCLUDED.full_name),
    role = 'owner',
    updated_at = now();

  INSERT INTO public.org_billing (
    org_id,
    plan_code,
    billing_status,
    current_period_end,
    cancel_at_period_end
  ) VALUES (
    v_org_id,
    'node',
    'trialing',
    v_trial_end,
    false
  )
  ON CONFLICT (org_id) DO UPDATE SET
    plan_code = COALESCE(public.org_billing.plan_code, 'node'),
    billing_status = CASE
      WHEN public.org_billing.billing_status IN ('active', 'trialing') THEN public.org_billing.billing_status
      ELSE 'trialing'
    END,
    current_period_end = COALESCE(public.org_billing.current_period_end, EXCLUDED.current_period_end),
    cancel_at_period_end = COALESCE(public.org_billing.cancel_at_period_end, false);

  INSERT INTO public.environments (org_id, name, is_active)
  VALUES (v_org_id, 'production', true)
  ON CONFLICT DO NOTHING;

  RETURN NEW;
END;
$$;
