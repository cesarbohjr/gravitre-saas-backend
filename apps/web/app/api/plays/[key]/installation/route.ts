import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { snakeToCamel } from "@/lib/supabase/transforms"

const MODES = ["OBSERVE", "RECOMMEND", "ACT WITH APPROVAL", "ACT WITHIN POLICY"] as const
type Mode = (typeof MODES)[number]

function validMode(value: unknown): value is Mode {
  return typeof value === "string" && MODES.includes(value as Mode)
}

export async function GET(request: NextRequest, context: { params: Promise<{ key: string }> }) {
  try {
    const { key } = await context.params
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) return NextResponse.json({ error: "Organization context required" }, { status: 403 })

    const { data, error } = await supabase
      .from("play_installations")
      .select("*")
      .eq("org_id", orgId)
      .eq("environment_name", "production")
      .eq("play_key", key)
      .maybeSingle()

    if (error) return NextResponse.json({ error: error.message }, { status: 500 })
    return NextResponse.json({ installation: data ? snakeToCamel<Record<string, unknown>>(data) : null })
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Unknown error" }, { status: 500 })
  }
}

export async function PUT(request: NextRequest, context: { params: Promise<{ key: string }> }) {
  try {
    const { key } = await context.params
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) return NextResponse.json({ error: "Organization context required" }, { status: 403 })

    const body = await request.json() as Record<string, unknown>
    const playVersion = String(body.playVersion ?? "").trim()
    const operatingMode = body.operatingMode ?? "OBSERVE"
    if (!playVersion) return NextResponse.json({ error: "playVersion is required" }, { status: 400 })
    if (!validMode(operatingMode)) return NextResponse.json({ error: "Invalid operating mode" }, { status: 400 })

    const payload = {
      org_id: orgId,
      environment_name: "production",
      play_key: key,
      play_version: playVersion,
      goal_id: typeof body.goalId === "string" && body.goalId ? body.goalId : null,
      operating_mode: operatingMode,
      status: typeof body.status === "string" ? body.status : "draft",
      configuration: typeof body.configuration === "object" && body.configuration ? body.configuration : {},
      updated_at: new Date().toISOString(),
    }
    const { data, error } = await supabase
      .from("play_installations")
      .upsert(payload, { onConflict: "org_id,environment_name,play_key" })
      .select("*")
      .single()

    if (error) return NextResponse.json({ error: error.message }, { status: 500 })
    return NextResponse.json({ installation: snakeToCamel<Record<string, unknown>>(data) })
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Unknown error" }, { status: 500 })
  }
}
