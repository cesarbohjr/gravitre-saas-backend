/**
 * Server-side B1 voice CONFIGURE gate for Next agent routes.
 * Mirrors backend assert_voice_configure (full / org admin / dept manager).
 */
import type { SupabaseClient } from "@supabase/supabase-js"

export async function assertCanConfigureVoice(
  supabase: SupabaseClient,
  orgId: string,
  userId: string | null | undefined,
): Promise<{ ok: true } | { ok: false; status: number; error: string; reason: string }> {
  if (!userId) {
    return {
      ok: false,
      status: 401,
      error: "Authentication required",
      reason: "unauthenticated",
    }
  }

  const { data: orgMember } = await supabase
    .from("organization_members")
    .select("role")
    .eq("org_id", orgId)
    .eq("user_id", userId)
    .maybeSingle()

  const orgRole = String(orgMember?.role || "").toLowerCase()
  if (orgRole === "owner" || orgRole === "admin") {
    return { ok: true }
  }

  const { data: deptRows } = await supabase
    .from("department_members")
    .select("role, departments!inner(id, org_id)")
    .eq("user_id", userId)

  const managerInOrg = (deptRows || []).some((row) => {
    const dept = row.departments as { org_id?: string } | { org_id?: string }[] | null
    const orgMatch = Array.isArray(dept)
      ? dept.some((d) => String(d?.org_id) === orgId)
      : String(dept?.org_id || "") === orgId
    return orgMatch && String(row.role || "").toLowerCase() === "admin"
  })

  if (managerInOrg) {
    return { ok: true }
  }

  // No department membership → treated as full seat elsewhere; allow configure.
  const inAnyDeptForOrg = (deptRows || []).some((row) => {
    const dept = row.departments as { org_id?: string } | { org_id?: string }[] | null
    return Array.isArray(dept)
      ? dept.some((d) => String(d?.org_id) === orgId)
      : String(dept?.org_id || "") === orgId
  })
  if (!inAnyDeptForOrg && orgMember) {
    return { ok: true }
  }

  return {
    ok: false,
    status: 403,
    error: "Full or manager seat required for voice configuration",
    reason: "lite_seat_blocked",
  }
}

export function voiceProfileIsConfigured(profile: unknown): boolean {
  if (!profile || typeof profile !== "object") return false
  const p = profile as Record<string, unknown>
  return Boolean(p.voice_id || p.voice_key || p.voiceId || p.voiceKey)
}
