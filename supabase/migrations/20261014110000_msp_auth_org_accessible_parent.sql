-- Release 4 (Option A): MSP parent org members may access child org rows via auth_org_accessible.
-- Application still gates API org resolution with MSP_PARENT_ORG_ENABLED until product sign-off.

CREATE OR REPLACE FUNCTION public.auth_org_accessible(target_org_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.organization_members om
    INNER JOIN public.organizations o ON o.id = om.org_id
    WHERE om.user_id = auth.uid()
      AND om.org_id = target_org_id
      AND o.data_region = public.deployment_data_region()
  )
  OR EXISTS (
    SELECT 1
    FROM public.organizations child
    INNER JOIN public.organization_members parent_member
      ON parent_member.org_id = child.parent_org_id
    INNER JOIN public.organizations parent_org ON parent_org.id = child.parent_org_id
    WHERE child.id = target_org_id
      AND child.parent_org_id IS NOT NULL
      AND parent_member.user_id = auth.uid()
      AND child.data_region = public.deployment_data_region()
      AND parent_org.data_region = public.deployment_data_region()
  );
$$;

COMMENT ON FUNCTION public.auth_org_accessible(uuid) IS
  'Member of org, or member of MSP parent org (parent_org_id) for child org access.';
