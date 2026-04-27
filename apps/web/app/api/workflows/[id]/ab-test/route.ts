import { NextRequest, NextResponse } from "next/server"
import { camelToSnake, snakeToCamel } from "@/lib/supabase/transforms"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"

interface RouteParams {
  params: Promise<{ id: string }>
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  try {
    const { id } = await params
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const body = (await request.json()) as Record<string, unknown>
    const snake = camelToSnake(body)
    const versionA = Number(snake.version_a ?? snake.versionA)
    const versionB = Number(snake.version_b ?? snake.versionB)
    if (!Number.isFinite(versionA) || !Number.isFinite(versionB)) {
      return NextResponse.json({ error: "versionA and versionB are required numbers" }, { status: 400 })
    }

    const payload = {
      org_id: orgId,
      workflow_id: id,
      version_a: versionA,
      version_b: versionB,
      traffic_split: (snake.traffic_split as Record<string, unknown> | undefined) ?? snake.trafficSplit ?? {},
      metrics: (snake.metrics as Record<string, unknown> | undefined) ?? {},
      status: (snake.status as string | undefined) ?? "draft",
    }

    const { data, error } = await supabase.from("workflow_ab_tests").insert(payload).select("*").single()
    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ abTest: snakeToCamel<Record<string, unknown>>(data) }, { status: 201 })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
