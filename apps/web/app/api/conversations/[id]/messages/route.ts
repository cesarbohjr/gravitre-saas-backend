import { NextRequest, NextResponse } from "next/server"
import { mapConversationMessageRow } from "@/lib/conversations-data"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
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

    const { id } = await params
    const { data: conversation, error: conversationError } = await supabase
      .from("conversations")
      .select("id")
      .eq("id", id)
      .eq("org_id", orgId)
      .eq("user_id", userData.user.id)
      .maybeSingle()

    if (conversationError) {
      return NextResponse.json({ error: conversationError.message }, { status: 500 })
    }
    if (!conversation) {
      return NextResponse.json({ error: "Conversation not found" }, { status: 404 })
    }

    const { data, error } = await supabase
      .from("conversation_messages")
      .select("id, conversation_id, role, content, tool_calls, created_at")
      .eq("conversation_id", id)
      .order("created_at", { ascending: true })

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({
      messages: (data ?? []).map((row) =>
        mapConversationMessageRow(row as Parameters<typeof mapConversationMessageRow>[0])
      ),
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
