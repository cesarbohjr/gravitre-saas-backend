-- RB-00: Harden organization_members.role as closed enum (admin | member).
-- BE-20 approver_roles align to this set. No viewer in baseline.
-- Migrate any non-compliant roles to 'member' before adding constraint.

UPDATE public.organization_members
SET role = 'member'
WHERE role IS NULL OR role NOT IN ('admin', 'member');

ALTER TABLE public.organization_members
  DROP CONSTRAINT IF EXISTS organization_members_role_check;

ALTER TABLE public.organization_members
  ADD CONSTRAINT organization_members_role_check
  CHECK (role IN ('admin', 'member'));
