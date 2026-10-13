import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { ensureDemoDataForOrg } from "@/lib/supabase/demo-bootstrap"
import { callFastApiAsCaller, proxyToFastApi } from "@/lib/backend-proxy"
import { camelToSnake, snakeToCamel } from "@/lib/supabase/transforms"

function normalizeUserRole(role: unknown): "owner" | "admin" | "member" | "viewer" {
  const value = String(role ?? "member").trim().toLowerCase()
  if (value === "owner") return "owner"
  if (value === "admin") return "admin"
  if (value === "viewer") return "viewer"
  return "member"
}

export async function GET(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }
    await ensureDemoDataForOrg(supabase, orgId)

    const { data: members, error: membersError } = await supabase
      .from("organization_members")
      .select("id, org_id, user_id, role, created_at")
      .eq("org_id", orgId)
      .order("created_at", { ascending: false })

    if (membersError) {
      return NextResponse.json({ error: membersError.message }, { status: 500 })
    }

    // organization_members.user_id stores the auth UID; public.users links via auth_user_id.
    const authUserIds = Array.from(
      new Set((members ?? []).map((member) => member.user_id).filter(Boolean)),
    )
    type TeamUserRow = {
      id: string
      auth_user_id?: string | null
      email?: string | null
      full_name?: string | null
      avatar_url?: string | null
      job_title?: string | null
      department?: string | null
    }
    let usersByAuthId: Record<string, TeamUserRow> = {}
    if (authUserIds.length > 0) {
      const { data: users } = await supabase
        .from("users")
        .select("id, auth_user_id, email, full_name, avatar_url, job_title, department")
        .in("auth_user_id", authUserIds)
      usersByAuthId = Object.fromEntries(
        (users ?? [])
          .filter((user) => user.auth_user_id)
          .map((user) => [String(user.auth_user_id), user as TeamUserRow]),
      )
    }

    let team = (members ?? []).map((member) => {
      const authUserId = String(member.user_id)
      const user = usersByAuthId[authUserId]
      return {
        // Prefer public.users.id so PATCH/DELETE against /api/settings/team keep working.
        id: user?.id ?? member.id,
        membershipId: member.id,
        orgId,
        userId: authUserId,
        role: normalizeUserRole(member.role),
        createdAt: member.created_at ?? null,
        email: user?.email ?? null,
        name: user?.full_name ?? null,
        full_name: user?.full_name ?? null,
        avatar_url: user?.avatar_url ?? null,
        job_title: user?.job_title ?? null,
        department: user?.department ?? null,
      }
    })

    if (team.length === 0) {
      const { data: orgUsers } = await supabase
        .from("users")
        .select("id, auth_user_id, email, full_name, avatar_url, job_title, department, role, created_at")
        .eq("org_id", orgId)
        .order("created_at", { ascending: false })
        .limit(20)

      team = (orgUsers ?? []).map((user) => ({
        id: user.id,
        membershipId: null,
        orgId,
        userId: user.auth_user_id ?? user.id,
        role: normalizeUserRole(user.role),
        createdAt: user.created_at ?? null,
        email: user.email ?? null,
        name: user.full_name ?? null,
        full_name: user.full_name ?? null,
        avatar_url: user.avatar_url ?? null,
        job_title: user.job_title ?? null,
        department: user.department ?? null,
      }))
    }

    return NextResponse.json({ team })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }
    return proxyToFastApi(request, `/api/organizations/${encodeURIComponent(orgId)}/members/invite`)
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }
    await ensureDemoDataForOrg(supabase, orgId)

    const body = await request.json().catch(() => ({}))
    const snake = camelToSnake(body as Record<string, unknown>)
    const id = snake.id ? String(snake.id) : null
    const email = snake.email ? String(snake.email).trim().toLowerCase() : null

    if (!id && !email) {
      return NextResponse.json({ error: "id or email is required" }, { status: 400 })
    }

    const updates: Record<string, unknown> = {}
    if (snake.role !== undefined) updates.role = normalizeUserRole(snake.role)
    if (snake.full_name !== undefined || snake.name !== undefined) {
      updates.full_name = String(snake.full_name ?? snake.name ?? "").trim() || null
    }
    if (snake.status !== undefined) {
      updates.status = String(snake.status ?? "active")
    }

    if (Object.keys(updates).length === 0) {
      return NextResponse.json({ error: "No updatable fields provided" }, { status: 400 })
    }

    // Role changes are an admin action. The membership row is the source of
    // truth for permissions, so it is changed by the backend (admin check, last
    // admin guard, audit) before the display copy in public.users is touched.
    // Members used to be able to promote themselves here.
    if (updates.role !== undefined) {
      const { data: authData } = await supabase.auth.getUser()
      const callerId = authData.user?.id
      if (!callerId) {
        return NextResponse.json({ error: "Authentication required" }, { status: 401 })
      }
      const { data: callerMembership } = await supabase
        .from("organization_members")
        .select("role")
        .eq("org_id", orgId)
        .eq("user_id", callerId)
        .maybeSingle()
      const callerRole = String(callerMembership?.role ?? "").toLowerCase()
      if (callerRole !== "owner" && callerRole !== "admin") {
        return NextResponse.json({ error: "Only an org admin can change roles" }, { status: 403 })
      }
      if (updates.role === "owner") {
        return NextResponse.json({ error: "Ownership cannot be assigned here" }, { status: 400 })
      }

      let target = supabase.from("users").select("auth_user_id").eq("org_id", orgId)
      target = id ? target.eq("id", id) : target.eq("email", email ?? "")
      const { data: targetUser } = await target.maybeSingle()
      if (!targetUser?.auth_user_id) {
        return NextResponse.json({ error: "Member not found" }, { status: 404 })
      }
      const { data: membership } = await supabase
        .from("organization_members")
        .select("id")
        .eq("org_id", orgId)
        .eq("user_id", targetUser.auth_user_id)
        .maybeSingle()
      if (!membership?.id) {
        return NextResponse.json({ error: "Member not found" }, { status: 404 })
      }
      const roleChange = await callFastApiAsCaller(
        request,
        `/api/org/members/${encodeURIComponent(String(membership.id))}`,
        "PATCH",
        { role: updates.role },
        orgId,
      )
      if (!roleChange.ok) {
        return NextResponse.json(roleChange.payload ?? { error: "Role change failed" }, {
          status: roleChange.status,
        })
      }
    }

    let query = supabase
      .from("users")
      .update(updates)
      .eq("org_id", orgId)

    query = id ? query.eq("id", id) : query.eq("email", email ?? "")

    const { data, error } = await query
      .select("id, org_id, auth_user_id, email, full_name, avatar_url, job_title, department, role, status, created_at, updated_at")
      .single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ member: snakeToCamel<Record<string, unknown>>(data) })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }
    await ensureDemoDataForOrg(supabase, orgId)

    const body = await request.json().catch(() => ({}))
    const id = body?.id ? String(body.id) : null
    const email = body?.email ? String(body.email).trim().toLowerCase() : null

    if (!id && !email) {
      return NextResponse.json({ error: "id or email is required" }, { status: 400 })
    }

    let query = supabase.from("users").delete().eq("org_id", orgId)
    query = id ? query.eq("id", id) : query.eq("email", email ?? "")

    const { error } = await query
    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ success: true })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
