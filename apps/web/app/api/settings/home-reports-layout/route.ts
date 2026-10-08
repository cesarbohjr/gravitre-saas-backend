import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { parseReportsLayout } from "@/lib/dashboard/home-reports"

/** Home dashboard Reports layout (range, view preset, widget order), per user and org. */
async function context(request: NextRequest) {
  const supabase = createSupabaseRouteClient(request)
  const {
    data: { user },
  } = await supabase.auth.getUser()
  if (!user) return { error: NextResponse.json({ error: "Unauthorized" }, { status: 401 }) }
  const orgId = await resolveOrgId(supabase, request)
  if (!orgId) return { error: NextResponse.json({ error: "Organization context required" }, { status: 403 }) }
  return { supabase, userId: user.id, orgId }
}

export async function GET(request: NextRequest) {
  try {
    const ctx = await context(request)
    if ("error" in ctx) return ctx.error
    const { data, error } = await ctx.supabase
      .from("user_ui_preferences")
      .select("preferences")
      .eq("org_id", ctx.orgId)
      .eq("user_id", ctx.userId)
      .maybeSingle()
    if (error) return NextResponse.json({ layout: null, warning: error.message })
    const prefs = (data?.preferences as Record<string, unknown> | null) ?? {}
    return NextResponse.json({ layout: parseReportsLayout(prefs.homeReports) })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error", layout: null },
      { status: 500 },
    )
  }
}

export async function PUT(request: NextRequest) {
  try {
    const ctx = await context(request)
    if ("error" in ctx) return ctx.error
    const body = await request.json().catch(() => ({}))
    const layout = parseReportsLayout(body?.layout)
    if (!layout) return NextResponse.json({ error: "Invalid layout" }, { status: 400 })

    const { data: existing } = await ctx.supabase
      .from("user_ui_preferences")
      .select("preferences")
      .eq("org_id", ctx.orgId)
      .eq("user_id", ctx.userId)
      .maybeSingle()
    const prev = (existing?.preferences as Record<string, unknown> | null) ?? {}
    const now = new Date().toISOString()
    const homeReports = { ...layout, updatedAt: now }
    const { error } = await ctx.supabase.from("user_ui_preferences").upsert(
      { org_id: ctx.orgId, user_id: ctx.userId, preferences: { ...prev, homeReports }, updated_at: now },
      { onConflict: "org_id,user_id" },
    )
    if (error) return NextResponse.json({ error: error.message, saved: false }, { status: 500 })
    return NextResponse.json({ saved: true, layout: homeReports })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error", saved: false },
      { status: 500 },
    )
  }
}
