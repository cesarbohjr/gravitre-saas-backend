import { NextRequest, NextResponse } from "next/server"
import { mapConversationRow } from "@/lib/conversations-data"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"

export async function GET(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const { data: userData, error: userError } = await supabase.auth.getUser()
    if (userError || !userData.user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const { data, error } = await supabase
      .from("conversations")
      .select("id, title, preview, message_count, created_at, updated_at")
      .eq("org_id", orgId)
      .eq("user_id", userData.user.id)
      .order("updated_at", { ascending: false })

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({
      conversations: (data ?? []).map((row) => mapConversationRow(row as Parameters<typeof mapConversationRow>[0])),
    })
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

    const { data: userData, error: userError } = await supabase.auth.getUser()
    if (userError || !userData.user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const body = (await request.json().catch(() => ({}))) as { title?: string }
    const title = typeof body.title === "string" ? body.title.trim() : ""
    const now = new Date().toISOString()

    const { data, error } = await supabase
      .from("conversations")
      .insert({
        org_id: orgId,
        user_id: userData.user.id,
        title: title || "New conversation",
        preview: null,
        message_count: 0,
        created_at: now,
        updated_at: now,
      })
      .select("id, title, preview, message_count, created_at, updated_at")
      .single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json(mapConversationRow(data as Parameters<typeof mapConversationRow>[0]), { status: 201 })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
