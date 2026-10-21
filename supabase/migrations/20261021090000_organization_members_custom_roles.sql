-- Custom roles (Trust & Safety > Role permissions).
--
-- A workspace can define its own roles next to owner/admin/member/viewer. Their
-- definitions and capabilities live in organizations.settings->'role_permissions'
-- and the API checks that a role exists in the workspace before anyone is put on
-- it. The table only checks the key's shape: lowercase letters, digits and
-- underscores, starting with a letter, at most 40 characters.
--
-- Existing rows all satisfy the new check (they are owner/admin/member/viewer),
-- so no data changes. To roll back, move anyone on a custom role to a built in
-- role first, then restore the previous constraint:
--   CHECK (role IN ('owner', 'admin', 'member', 'viewer'))

ALTER TABLE public.organization_members
  DROP CONSTRAINT IF EXISTS organization_members_role_check;

ALTER TABLE public.organization_members
  ADD CONSTRAINT organization_members_role_check
  CHECK (role ~ '^[a-z][a-z0-9_]{0,39}$');
