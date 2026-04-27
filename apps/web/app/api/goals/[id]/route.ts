import { NextRequest, NextResponse } from "next/server"
import { camelToSnake, snakeToCamel } from "@/lib/supabase/transforms"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"

interface RouteParams {
  params: Promise<{ id: string }>
}

export async function PATCH(request: NextRequest, { params }: RouteParams) {
  try {
    const { id } = await params
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const body = (await request.json()) as Record<string, unknown>
    const snake = camelToSnake(body)
    const payload: Record<string, unknown> = {}

    if (snake.objective !== undefined) payload.objective = snake.objective
    if (snake.category !== undefined) payload.category = snake.category
    if (snake.priority !== undefined) payload.priority = snake.priority
    if (snake.frequency !== undefined) payload.frequency = snake.frequency
    if (snake.department !== undefined) payload.department = snake.department
    if (snake.status !== undefined) payload.status = snake.status
    if (snake.connected_systems !== undefined) payload.connected_systems = snake.connected_systems
    if (snake.connectedSystems !== undefined) payload.connected_systems = snake.connectedSystems
    if (snake.success_metrics !== undefined) payload.success_metrics = snake.success_metrics
    if (snake.successMetrics !== undefined) payload.success_metrics = snake.successMetrics

    if (Object.keys(payload).length === 0) {
      return NextResponse.json({ error: "No updatable fields were provided" }, { status: 400 })
    }

    const { data, error } = await supabase
      .from("goals")
      .update(payload)
      .eq("org_id", orgId)
      .eq("id", id)
      .select("*")
      .single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ goal: snakeToCamel<Record<string, unknown>>(data) })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
