-- Ensure cesar@gravitre.app (and the gmail alias) have platform admin + org owner.
-- Idempotent: safe if already applied via earlier seeds.

DO $$
DECLARE
  v_user_id uuid;
  v_email text;
  v_org_id uuid;
BEGIN
  FOR v_email IN
    SELECT unnest(ARRAY['cesar@gravitre.app', 'cesar.bohorquez.jr@gmail.com'])
  LOOP
    SELECT id INTO v_user_id
    FROM auth.users
    WHERE lower(email) = lower(v_email)
    LIMIT 1;

    IF v_user_id IS NULL THEN
      RAISE NOTICE 'platform_admin: auth user % not found yet — skip', v_email;
      CONTINUE;
    END IF;

    INSERT INTO public.platform_admins (user_id, email, notes)
    VALUES (v_user_id, v_email, 'Gravitre master admin')
    ON CONFLICT (user_id) DO UPDATE
      SET email = EXCLUDED.email,
          notes = EXCLUDED.notes;

    -- Prefer the user's current org from public.users; else earliest membership; else leave membership alone.
    SELECT u.org_id INTO v_org_id
    FROM public.users u
    WHERE u.auth_user_id = v_user_id
    LIMIT 1;

    IF v_org_id IS NULL THEN
      SELECT om.org_id INTO v_org_id
      FROM public.organization_members om
      WHERE om.user_id = v_user_id
      ORDER BY om.created_at ASC NULLS LAST
      LIMIT 1;
    END IF;

    IF v_org_id IS NOT NULL THEN
      INSERT INTO public.organization_members (org_id, user_id, role)
      VALUES (v_org_id, v_user_id, 'owner')
      ON CONFLICT (org_id, user_id) DO UPDATE SET role = 'owner';

      UPDATE public.users
      SET role = 'owner', status = 'active', org_id = v_org_id
      WHERE auth_user_id = v_user_id;

      IF NOT FOUND AND to_regclass('public.users') IS NOT NULL THEN
        INSERT INTO public.users (org_id, auth_user_id, email, full_name, role, status)
        VALUES (
          v_org_id,
          v_user_id,
          v_email,
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

    RAISE NOTICE 'platform_admin: granted owner + platform_admins for % user_id=% org_id=%',
      v_email, v_user_id, v_org_id;
  END LOOP;
END $$;
