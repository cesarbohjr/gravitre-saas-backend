import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { syncOperatorMirror } from "@/lib/agent-operator-mirror"
import { isAgentAvatarColorId, isAgentIconId } from "@/lib/agent-identity"

interface RouteParams {
  params: Promise<{ id: string }>
}

const MAX_BYTES = 5 * 1024 * 1024

function mapAgentRow(input: Record<string, unknown>) {
  const personality =
    input.personality && typeof input.personality === "object"
      ? (input.personality as Record<string, unknown>)
      : {}
  return {
    id: String(input.id),
    name: String(input.name ?? "Agent"),
    icon: isAgentIconId(String(input.icon ?? "")) ? String(input.icon) : null,
    avatarColor: isAgentAvatarColorId(String(input.avatar_color ?? input.avatarColor ?? ""))
      ? String(input.avatar_color ?? input.avatarColor)
      : null,
    avatarUrl: typeof input.avatar_url === "string" ? input.avatar_url : null,
    personality,
  }
}

async function updateAvatarUrl(
  request: NextRequest,
  id: string,
  avatarUrl: string | null,
) {
  const supabase = createSupabaseRouteClient(request)
  const orgId = await resolveOrgId(supabase, request)
  if (!orgId) {
    return NextResponse.json({ error: "Organization context required" }, { status: 403 })
  }

  const { data, error } = await supabase
    .from("agents")
    .update({
      avatar_url: avatarUrl,
      updated_at: new Date().toISOString(),
    })
    .eq("org_id", orgId)
    .eq("id", id)
    .select("*")
    .single()

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }
  if (!data) {
    return NextResponse.json({ error: "Agent not found" }, { status: 404 })
  }

  const { data: userData } = await supabase.auth.getUser()
  await syncOperatorMirror(supabase, orgId, data as Record<string, unknown>, userData.user?.id ?? null)

  return NextResponse.json({
    agent: mapAgentRow(data as Record<string, unknown>),
    avatarUrl,
  })
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const { id } = await params
  const form = await request.formData().catch(() => null)
  const file = form?.get("avatar")
  if (!(file instanceof File)) {
    return NextResponse.json({ error: "Avatar file required" }, { status: 400 })
  }
  if (file.size <= 0) {
    return NextResponse.json({ error: "Avatar file is empty" }, { status: 400 })
  }
  if (file.size > MAX_BYTES) {
    return NextResponse.json({ error: "Avatar exceeds 5MB limit" }, { status: 400 })
  }

  const buffer = Buffer.from(await file.arrayBuffer())
  const mime = file.type || "image/png"
  if (!mime.startsWith("image/")) {
    return NextResponse.json({ error: "Avatar must be an image" }, { status: 400 })
  }
  const avatarDataUrl = `data:${mime};base64,${buffer.toString("base64")}`
  return updateAvatarUrl(request, id, avatarDataUrl)
}

export async function DELETE(request: NextRequest, { params }: RouteParams) {
  const { id } = await params
  return updateAvatarUrl(request, id, null)
}
