import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { camelToSnake, snakeToCamel } from "@/lib/supabase/transforms"

function mapWorkflowRow(input: Record<string, unknown>) {
  const model = snakeToCamel<Record<string, unknown>>(input)
  return {
    id: String(model.id),
    name: String(model.name ?? "workflow"),
    description: String(model.description ?? ""),
    status: String(model.status ?? "draft"),
    environment: String(model.environment ?? "production"),
    lastRun: "Never",
    successRate: "-",
    runCount: 0,
    nodes: Array.isArray(model.nodes) ? model.nodes : undefined,
    isRunning: false,
    createdAt: model.createdAt ?? model.created_at,
    updatedAt: model.updatedAt ?? model.updated_at,
  }
}

export async function GET(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const { data, error } = await supabase
      .from("workflows")
      .select("*")
      .eq("org_id", orgId)
      .order("created_at", { ascending: false })

    if (error) {
      return NextResponse.json({ error: error.message, workflows: [] }, { status: 500 })
    }

    const workflows = (data ?? []).map((row) => mapWorkflowRow(row as Record<string, unknown>))
    return NextResponse.json({ workflows })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error", workflows: [] },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const body = await request.json()
    const snake = camelToSnake(body as Record<string, unknown>)
    const { data: userData } = await supabase.auth.getUser()

    const insertPayload = {
      org_id: orgId,
      name: String(snake.name ?? "New Workflow"),
      description: (snake.description as string | undefined) ?? null,
      status: "draft",
      environment: (snake.environment as string | undefined) ?? "production",
      nodes: Array.isArray(snake.nodes) ? snake.nodes : [],
      edges: Array.isArray(snake.edges) ? snake.edges : [],
      config: snake.config && typeof snake.config === "object" ? snake.config : {},
      created_by: userData.user?.id ?? null,
    }

    const { data, error } = await supabase
      .from("workflows")
      .insert(insertPayload)
      .select("*")
      .single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json(mapWorkflowRow(data as Record<string, unknown>), { status: 201 })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
