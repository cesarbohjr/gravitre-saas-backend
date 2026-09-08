import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"

type DashboardLayoutBody = {
  version?: number
  globalRange?: string
  widgets?: unknown[]
  updatedAt?: string
}

function isValidLayout(layout: unknown): layout is DashboardLayoutBody {
  if (!layout || typeof layout !== "object") return false
  const l = layout as DashboardLayoutBody
  return l.version === 1 && Array.isArray(l.widgets)
}

export async function GET(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const {
      data: { user },
    } = await supabase.auth.getUser()
    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const { data, error } = await supabase
      .from("user_ui_preferences")
      .select("preferences")
      .eq("org_id", orgId)
      .eq("user_id", user.id)
      .maybeSingle()

    if (error) {
      // Table may not exist yet in some envs — soft-fail to local-only.
      return NextResponse.json({ layout: null, warning: error.message })
    }

    const prefs = (data?.preferences as Record<string, unknown> | null) ?? {}
    const layout = prefs.homeDashboard ?? null
    return NextResponse.json({
      layout: isValidLayout(layout) ? layout : null,
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error", layout: null },
      { status: 500 },
    )
  }
}

export async function PUT(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const {
      data: { user },
    } = await supabase.auth.getUser()
    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const body = await request.json().catch(() => ({}))
    const layout = body?.layout
    if (!isValidLayout(layout)) {
      return NextResponse.json({ error: "Invalid layout" }, { status: 400 })
    }

    const { data: existing } = await supabase
      .from("user_ui_preferences")
      .select("preferences")
      .eq("org_id", orgId)
      .eq("user_id", user.id)
      .maybeSingle()

    const prev = (existing?.preferences as Record<string, unknown> | null) ?? {}
    const nextPrefs = {
      ...prev,
      homeDashboard: {
        ...layout,
        updatedAt: new Date().toISOString(),
      },
    }

    const { error } = await supabase.from("user_ui_preferences").upsert(
      {
        org_id: orgId,
        user_id: user.id,
        preferences: nextPrefs,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "org_id,user_id" },
    )

    if (error) {
      return NextResponse.json({ error: error.message, saved: false }, { status: 500 })
    }

    return NextResponse.json({ saved: true, layout: nextPrefs.homeDashboard })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error", saved: false },
      { status: 500 },
    )
  }
}
