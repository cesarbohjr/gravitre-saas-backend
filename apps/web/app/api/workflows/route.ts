import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { camelToSnake, snakeToCamel } from "@/lib/supabase/transforms"
import { proxyToFastApi, syncWorkflowSchemaFromContract } from "@/lib/backend-proxy"

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

// The workflow set, Lite-seat filtering and run stats come from the core list
// (backend/app/routers/workflows.py list_workflows_route). Only the canvas
// `nodes`, which the core list omits, are joined from the contract rows.
export async function GET(request: NextRequest) {
  try {
    const upstream = await proxyToFastApi(request, "/api/workflows")
    if (!upstream.ok) return upstream
    const payload = (await upstream.json()) as { workflows?: Array<Record<string, unknown>> }
    const workflows = Array.isArray(payload.workflows) ? payload.workflows : []
    const ids = workflows.map((w) => String(w.id ?? "")).filter(Boolean)
    if (ids.length === 0) return NextResponse.json({ workflows })

    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    const nodesById = new Map<string, unknown>()
    if (orgId) {
      const { data } = await supabase.from("workflows").select("id, nodes").eq("org_id", orgId).in("id", ids)
      for (const row of (data ?? []) as Array<{ id: string; nodes: unknown }>) {
        if (Array.isArray(row.nodes)) nodesById.set(String(row.id), row.nodes)
      }
    }
    return NextResponse.json({
      workflows: workflows.map((w) => ({ ...w, nodes: nodesById.get(String(w.id)) })),
    })
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

    const workflowId = String((data as Record<string, unknown>).id)
    await syncWorkflowSchemaFromContract(request, workflowId)

    return NextResponse.json(mapWorkflowRow(data as Record<string, unknown>), { status: 201 })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
