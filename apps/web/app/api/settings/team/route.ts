import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { ensureDemoDataForOrg } from "@/lib/supabase/demo-bootstrap"
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
    await ensureDemoDataForOrg(supabase, orgId)

    const body = await request.json().catch(() => ({}))
    const snake = camelToSnake(body as Record<string, unknown>)
    const email = String(snake.email ?? "").trim().toLowerCase()
    if (!email) {
      return NextResponse.json({ error: "email is required" }, { status: 400 })
    }

    const role = normalizeUserRole(snake.role)
    const fullName = String(snake.full_name ?? snake.name ?? "").trim() || email.split("@")[0]

    const { data, error } = await supabase
      .from("users")
      .upsert(
        {
          org_id: orgId,
          email,
          full_name: fullName,
          role,
          status: "invited",
        },
        { onConflict: "org_id,email" }
      )
      .select("id, org_id, email, full_name, role, status, created_at, updated_at")
      .single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ member: snakeToCamel<Record<string, unknown>>(data) }, { status: 201 })
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

    // Keep organization_members.role in sync when role changes — that is the
    // membership source of truth used by GET /api/settings/team.
    if (updates.role !== undefined && data?.auth_user_id) {
      await supabase
        .from("organization_members")
        .update({ role: updates.role })
        .eq("org_id", orgId)
        .eq("user_id", data.auth_user_id)
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
