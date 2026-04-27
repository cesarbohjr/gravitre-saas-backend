import { NextRequest, NextResponse } from "next/server"
import { camelToSnake, snakeToCamel } from "@/lib/supabase/transforms"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"

export async function POST(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const body = (await request.json()) as Record<string, unknown>
    const snake = camelToSnake(body)
    const payload = {
      org_id: orgId,
      objective: String(snake.objective ?? "").trim(),
      category: (snake.category as string | undefined) ?? null,
      priority: (snake.priority as string | undefined) ?? null,
      frequency: (snake.frequency as string | undefined) ?? null,
      department: (snake.department as string | undefined) ?? null,
      success_metrics:
        (snake.success_metrics as Record<string, unknown> | undefined) ??
        (snake.successMetrics as Record<string, unknown> | undefined) ??
        {},
      connected_systems:
        (snake.connected_systems as string[] | undefined) ??
        (snake.connectedSystems as string[] | undefined) ??
        [],
      status: (snake.status as string | undefined) ?? "draft",
    }

    if (!payload.objective) {
      return NextResponse.json({ error: "objective is required" }, { status: 400 })
    }

    const { data, error } = await supabase.from("goals").insert(payload).select("*").single()
    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ goal: snakeToCamel<Record<string, unknown>>(data) }, { status: 201 })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
