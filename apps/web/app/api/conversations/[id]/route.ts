import { NextRequest, NextResponse } from "next/server"
import { mapConversationRow } from "@/lib/conversations-data"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"

async function requireConversationContext(request: NextRequest) {
  const supabase = createSupabaseRouteClient(request)
  const orgId = await resolveOrgId(supabase, request)
  if (!orgId) {
    return { error: NextResponse.json({ error: "Organization context required" }, { status: 403 }) }
  }

  const { data: userData, error: userError } = await supabase.auth.getUser()
  if (userError || !userData.user) {
    return { error: NextResponse.json({ error: "Unauthorized" }, { status: 401 }) }
  }

  return { supabase, orgId, userId: userData.user.id }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const context = await requireConversationContext(request)
    if ("error" in context) return context.error

    const { id } = await params
    const { data, error } = await context.supabase
      .from("conversations")
      .select("id, title, preview, message_count, created_at, updated_at")
      .eq("id", id)
      .eq("org_id", context.orgId)
      .eq("user_id", context.userId)
      .maybeSingle()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }
    if (!data) {
      return NextResponse.json({ error: "Conversation not found" }, { status: 404 })
    }

    return NextResponse.json(mapConversationRow(data as Parameters<typeof mapConversationRow>[0]))
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const context = await requireConversationContext(request)
    if ("error" in context) return context.error

    const { id } = await params
    const body = (await request.json().catch(() => ({}))) as { title?: string }
    const updates: Record<string, string> = { updated_at: new Date().toISOString() }

    if (typeof body.title === "string") {
      const title = body.title.trim()
      if (!title) {
        return NextResponse.json({ error: "Title cannot be empty" }, { status: 400 })
      }
      updates.title = title
    }

    const { data, error } = await context.supabase
      .from("conversations")
      .update(updates)
      .eq("id", id)
      .eq("org_id", context.orgId)
      .eq("user_id", context.userId)
      .select("id, title, preview, message_count, created_at, updated_at")
      .maybeSingle()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }
    if (!data) {
      return NextResponse.json({ error: "Conversation not found" }, { status: 404 })
    }

    return NextResponse.json(mapConversationRow(data as Parameters<typeof mapConversationRow>[0]))
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const context = await requireConversationContext(request)
    if ("error" in context) return context.error

    const { id } = await params
    const { error, count } = await context.supabase
      .from("conversations")
      .delete({ count: "exact" })
      .eq("id", id)
      .eq("org_id", context.orgId)
      .eq("user_id", context.userId)

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }
    if (!count) {
      return NextResponse.json({ error: "Conversation not found" }, { status: 404 })
    }

    return new NextResponse(null, { status: 204 })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
