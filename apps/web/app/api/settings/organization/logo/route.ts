import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { snakeToCamel } from "@/lib/supabase/transforms"

const MAX_BYTES = 2 * 1024 * 1024

async function requireOrgAdmin(supabase: ReturnType<typeof createSupabaseRouteClient>, orgId: string, userId: string) {
  const { data, error } = await supabase
    .from("organization_members")
    .select("role")
    .eq("org_id", orgId)
    .eq("user_id", userId)
    .maybeSingle()
  if (error) {
    throw new Error(error.message)
  }
  if (!data || String(data.role).toLowerCase() !== "admin") {
    return false
  }
  return true
}

export async function POST(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const { data: userData } = await supabase.auth.getUser()
    const userId = userData.user?.id
    if (!userId) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const isAdmin = await requireOrgAdmin(supabase, orgId, userId)
    if (!isAdmin) {
      return NextResponse.json({ error: "Admin access required" }, { status: 403 })
    }

    const formData = await request.formData()
    const file = formData.get("logo")
    if (!(file instanceof File) || file.size === 0) {
      return NextResponse.json({ error: "Logo file is required" }, { status: 400 })
    }
    if (file.size > MAX_BYTES) {
      return NextResponse.json({ error: "Logo exceeds 2MB limit" }, { status: 400 })
    }

    const buffer = Buffer.from(await file.arrayBuffer())
    const mime = file.type || "image/png"
    const logoUrl = `data:${mime};base64,${buffer.toString("base64")}`

    const { data, error } = await supabase
      .from("organizations")
      .update({ logo_url: logoUrl })
      .eq("id", orgId)
      .select("*")
      .single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ organization: snakeToCamel<Record<string, unknown>>(data), logoUrl })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 },
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

    const { data: userData } = await supabase.auth.getUser()
    const userId = userData.user?.id
    if (!userId) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const isAdmin = await requireOrgAdmin(supabase, orgId, userId)
    if (!isAdmin) {
      return NextResponse.json({ error: "Admin access required" }, { status: 403 })
    }

    const { data, error } = await supabase
      .from("organizations")
      .update({ logo_url: null })
      .eq("id", orgId)
      .select("*")
      .single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ organization: snakeToCamel<Record<string, unknown>>(data), logoUrl: null })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 },
    )
  }
}
