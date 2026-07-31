import { createClient, type SupabaseClient } from "@supabase/supabase-js"

export interface ResolvedOrgMembership {
  org_id: string | null
  organizations: Array<{ id: string; name: string | null; role: string | null }>
  current_org: { id: string; name: string | null } | null
}

import { getSupabaseServiceUrl } from "@/lib/supabase/url"

function getServiceRoleKey(): string | null {
  return process.env.SUPABASE_SERVICE_ROLE_KEY?.trim() || null
}

function createServiceRoleClient(): SupabaseClient | null {
  const serviceKey = getServiceRoleKey()
  if (!serviceKey) return null
  return createClient(getSupabaseServiceUrl(), serviceKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  })
}

/** Server-only: load org memberships when the FastAPI backend is unavailable. */
export async function loadOrgMembershipsForAuthUser(
  authUserId: string,
): Promise<ResolvedOrgMembership> {
  const empty: ResolvedOrgMembership = {
    org_id: null,
    organizations: [],
    current_org: null,
  }

  const client = createServiceRoleClient()
  if (!client) return empty

  const { data: memberships, error: membershipError } = await client
    .from("organization_members")
    .select("org_id, role, created_at")
    .eq("user_id", authUserId)
    .order("created_at", { ascending: true })

  if (membershipError || !memberships?.length) {
    return empty
  }

  const orgIds = memberships.map((row) => String(row.org_id))
  const rolesByOrg = new Map(
    memberships.map((row) => [String(row.org_id), (row.role as string | null) ?? "member"]),
  )

  const { data: userRow } = await client
    .from("users")
    .select("org_id")
    .eq("auth_user_id", authUserId)
    .maybeSingle()

  const primaryOrgId = userRow?.org_id ? String(userRow.org_id) : null
  const preferredOrgId =
    (primaryOrgId && orgIds.includes(primaryOrgId) ? primaryOrgId : null) ??
    orgIds.find((id) => id !== "00000000-0000-0000-0000-000000000001" && id !== "11111111-1111-4111-8111-111111111111") ??
    orgIds[0] ??
    null

  const { data: orgRows } = await client
    .from("organizations")
    .select("id, name")
    .in("id", orgIds)

  const nameById = new Map(
    (orgRows ?? []).map((row) => [String(row.id), (row.name as string | null) ?? null]),
  )

  const organizations = orgIds.map((id) => ({
    id,
    name: nameById.get(id) ?? "Organization",
    role: rolesByOrg.get(id) ?? "member",
  }))

  const currentOrg =
    preferredOrgId != null
      ? { id: preferredOrgId, name: nameById.get(preferredOrgId) ?? "Organization" }
      : null

  return {
    org_id: preferredOrgId,
    organizations,
    current_org: currentOrg,
  }
}
