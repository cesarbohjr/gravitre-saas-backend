import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { ensureDemoDataForOrg } from "@/lib/supabase/demo-bootstrap"
import { camelToSnake, snakeToCamel } from "@/lib/supabase/transforms"

export async function GET(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }
    await ensureDemoDataForOrg(supabase, orgId)
    const { data, error } = await supabase
      .from("webhooks")
      .select("id, org_id, url, events, status, last_delivery_at, created_at, updated_at")
      .eq("org_id", orgId)
      .order("created_at", { ascending: false })
    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }
    return NextResponse.json({ webhooks: (data ?? []).map((row) => snakeToCamel<Record<string, unknown>>(row)) })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }
    const body = await request.json()
    const snake = camelToSnake(body as Record<string, unknown>)
    const hookId = String(snake.id ?? "")
    if (!hookId) {
      return NextResponse.json({ error: "id is required" }, { status: 400 })
    }
    const { data, error } = await supabase
      .from("webhooks")
      .update({
        status: snake.status ?? "active",
        events: snake.events ?? [],
      })
      .eq("org_id", orgId)
      .eq("id", hookId)
      .select("id, org_id, url, events, status, last_delivery_at, created_at, updated_at")
      .single()
    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }
    return NextResponse.json({ webhook: snakeToCamel<Record<string, unknown>>(data) })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
