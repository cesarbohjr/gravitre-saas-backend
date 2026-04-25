import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { snakeToCamel } from "@/lib/supabase/transforms"

export async function GET(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

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

    const team = (members ?? []).map((member) => {
      const base = snakeToCamel<Record<string, unknown>>(member)
      const user = usersById[String(member.user_id)] ?? {}
      return {
        ...base,
        email: user.email ?? null,
        name: user.full_name ?? null,
      }
    })

    return NextResponse.json({ team })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  void request
  return NextResponse.json(
    { message: "Invite flow is not implemented yet.", team: [] },
    { status: 501 }
  )
}
