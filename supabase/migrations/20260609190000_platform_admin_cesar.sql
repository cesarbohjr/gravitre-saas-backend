-- Platform master admin + ensure cesar.bohorquez.jr@gmail.com has owner access (idempotent).

CREATE TABLE IF NOT EXISTS public.platform_admins (
  user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email text NOT NULL UNIQUE,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.platform_admins IS
  'Gravitre platform operators with cross-org admin privileges (service-role managed).';

ALTER TABLE public.platform_admins ENABLE ROW LEVEL SECURITY;

-- Prod may still have RB-00 constraint (admin|member only); widen before granting owner.
ALTER TABLE public.organization_members
  DROP CONSTRAINT IF EXISTS organization_members_role_check;

ALTER TABLE public.organization_members
  ADD CONSTRAINT organization_members_role_check
  CHECK (role IN ('owner', 'admin', 'member', 'lite'));

DO $$
DECLARE
  v_user_id uuid;
  v_acme_org uuid := '00000000-0000-0000-0000-000000000001';
BEGIN
  SELECT id INTO v_user_id
  FROM auth.users
  WHERE lower(email) = lower('cesar.bohorquez.jr@gmail.com')
  LIMIT 1;

  IF v_user_id IS NULL THEN
    RAISE NOTICE 'platform_admin: auth user cesar.bohorquez.jr@gmail.com not found yet — run again after signup';
    RETURN;
  END IF;

  INSERT INTO public.platform_admins (user_id, email, notes)
  VALUES (v_user_id, 'cesar.bohorquez.jr@gmail.com', 'Gravitre master admin')
  ON CONFLICT (user_id) DO UPDATE
    SET email = EXCLUDED.email,
        notes = EXCLUDED.notes;

  INSERT INTO public.organization_members (org_id, user_id, role)
  VALUES (v_acme_org, v_user_id, 'owner')
  ON CONFLICT (org_id, user_id) DO UPDATE SET role = 'owner';

  IF to_regclass('public.users') IS NOT NULL THEN
    UPDATE public.users
    SET role = 'owner', status = 'active'
    WHERE auth_user_id = v_user_id;

    IF NOT FOUND THEN
      INSERT INTO public.users (org_id, auth_user_id, email, full_name, role, status)
      VALUES (
        v_acme_org,
        v_user_id,
        'cesar.bohorquez.jr@gmail.com',
        'Cesar Bohorquez',
        'owner',
        'active'
      )
      ON CONFLICT (auth_user_id) DO UPDATE
        SET role = 'owner',
            org_id = EXCLUDED.org_id,
            status = 'active';
    END IF;
  END IF;

  RAISE NOTICE 'platform_admin: granted owner + platform_admins for user_id=%', v_user_id;
END $$;
