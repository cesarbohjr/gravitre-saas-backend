import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { camelToSnake, snakeToCamel } from "@/lib/supabase/transforms"

interface RouteParams {
  params: Promise<{ id: string }>
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  try {
    const { id } = await params
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const { data, error } = await supabase
      .from("workflows")
      .select("*")
      .eq("org_id", orgId)
      .eq("id", id)
      .single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: error.code === "PGRST116" ? 404 : 500 })
    }

    const model = snakeToCamel<Record<string, unknown>>(data)
    return NextResponse.json({
      workflow: model,
      nodes: Array.isArray(model.nodes) ? model.nodes : [],
      edges: Array.isArray(model.edges) ? model.edges : [],
      config: (model.config as Record<string, unknown> | undefined) ?? {},
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}

export async function PUT(request: NextRequest, { params }: RouteParams) {
  try {
    const { id } = await params
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const body = await request.json()
    const snake = camelToSnake(body as Record<string, unknown>)
    const payload: Record<string, unknown> = {}

    if (snake.name !== undefined) payload.name = snake.name
    if (snake.description !== undefined) payload.description = snake.description
    if (snake.status !== undefined) payload.status = snake.status
    if (snake.environment !== undefined) payload.environment = snake.environment
    if (snake.nodes !== undefined) payload.nodes = snake.nodes
    if (snake.edges !== undefined) payload.edges = snake.edges
    if (snake.config !== undefined) payload.config = snake.config
    if (snake.definition && typeof snake.definition === "object") {
      const definition = snake.definition as Record<string, unknown>
      if (definition.nodes !== undefined) payload.nodes = definition.nodes
      if (definition.edges !== undefined) payload.edges = definition.edges
      if (definition.config !== undefined) payload.config = definition.config
    }

    const { data, error } = await supabase
      .from("workflows")
      .update(payload)
      .eq("org_id", orgId)
      .eq("id", id)
      .select("*")
      .single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json(snakeToCamel<Record<string, unknown>>(data))
  } catch (error) {
    return NextResponse.json(
      {
        error: "Failed to update workflow",
        detail: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    )
  }
}
