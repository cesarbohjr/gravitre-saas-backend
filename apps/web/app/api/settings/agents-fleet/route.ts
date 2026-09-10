import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import {
  normalizeAgentsFleetPrefs,
  type AgentsFleetPrefs,
} from "@/lib/agents-fleet-prefs"

/**
 * GET/PUT agents fleet UI prefs under user_ui_preferences.preferences.agentsFleet.
 * Soft-fails when the table is missing so localStorage remains the fallback.
 */
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
      return NextResponse.json({ prefs: null, warning: error.message })
    }

    const prefsBag = (data?.preferences as Record<string, unknown> | null) ?? {}
    const raw = prefsBag.agentsFleet
    return NextResponse.json({
      prefs: raw ? normalizeAgentsFleetPrefs(raw) : null,
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error", prefs: null },
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
    const prefs: AgentsFleetPrefs = normalizeAgentsFleetPrefs(body?.prefs)
    const stamped: AgentsFleetPrefs = {
      ...prefs,
      updatedAt: new Date().toISOString(),
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
      agentsFleet: stamped,
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

    return NextResponse.json({ saved: true, prefs: stamped })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error", saved: false },
      { status: 500 },
    )
  }
}
