-- STA-278: Canonical organization_members roles aligned with public.users (owner/admin/member/viewer).

UPDATE public.organization_members
SET role = 'viewer'
WHERE role = 'lite';

UPDATE public.organization_members
SET role = 'member'
WHERE role IS NULL
   OR role NOT IN ('owner', 'admin', 'member', 'viewer');

ALTER TABLE public.organization_members
  DROP CONSTRAINT IF EXISTS organization_members_role_check;

ALTER TABLE public.organization_members
  ADD CONSTRAINT organization_members_role_check
  CHECK (role IN ('owner', 'admin', 'member', 'viewer'));
