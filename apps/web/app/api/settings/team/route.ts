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

    const userIds = Array.from(new Set((members ?? []).map((member) => member.user_id).filter(Boolean)))
    let usersById: Record<string, { email?: string | null; full_name?: string | null }> = {}
    if (userIds.length > 0) {
      const { data: users } = await supabase
        .from("users")
        .select("id, email, full_name")
        .in("id", userIds)
      usersById = Object.fromEntries(
        (users ?? []).map((user) => [
          user.id,
          { email: user.email ?? null, full_name: user.full_name ?? null },
        ])
      )
    }

    let team = (members ?? []).map((member) => {
      const base = snakeToCamel<Record<string, unknown>>(member)
      const user = usersById[String(member.user_id)] ?? {}
      return {
        ...base,
        email: user.email ?? null,
        name: user.full_name ?? null,
      }
    })

    if (team.length === 0) {
      const { data: orgUsers } = await supabase
        .from("users")
        .select("id, email, full_name, role, created_at")
        .eq("org_id", orgId)
        .order("created_at", { ascending: false })
        .limit(20)

      team = (orgUsers ?? []).map((user) => ({
        id: user.id,
        orgId,
        userId: user.id,
        role: user.role ?? "member",
        createdAt: user.created_at ?? null,
        email: user.email ?? null,
        name: user.full_name ?? null,
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
      .select("id, org_id, email, full_name, role, status, created_at, updated_at")
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
