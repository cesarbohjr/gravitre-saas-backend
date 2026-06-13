import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, getRouteClientAuthMode, resolveOrgId } from "@/lib/supabase/server"
import { getOrgCountDiagnostics, isDebugRequest } from "@/lib/supabase/route-diagnostics"
import { camelToSnake, snakeToCamel } from "@/lib/supabase/transforms"

function mapAgentRow(input: Record<string, unknown>, knowledgeDocCount = 0) {
  const model = snakeToCamel<Record<string, unknown>>(input)
  const personality =
    model.personality && typeof model.personality === "object"
      ? (model.personality as Record<string, unknown>)
      : {}
  const stats = model.stats && typeof model.stats === "object" ? (model.stats as Record<string, unknown>) : {}

  return {
    id: String(model.id),
    name: String(model.name ?? "Agent"),
    role: String(model.role ?? model.name ?? "AI Agent"),
    department: String(model.department ?? "Operations"),
    description: String(model.description ?? model.purpose ?? "AI teammate"),
    status: String(model.status ?? "idle"),
    model: String(model.model ?? "auto"),
    knowledgeDocCount,
    personality: {
      color: String(personality.color ?? "blue"),
      gradient: String(personality.gradient ?? "from-blue-500 to-indigo-500"),
      glow: String(personality.glow ?? "shadow-blue-500/30"),
    },
    stats: {
      tasksToday: Number(stats.tasksToday ?? 0),
      successRate: Number(stats.successRate ?? 100),
      avgResponseTime: String(stats.avgResponseTime ?? "-"),
      workflowsUsing: Number(stats.workflowsUsing ?? 0),
      knowledgeDocCount,
    },
    capabilities: Array.isArray(model.capabilities) ? model.capabilities : [],
    permissions: Array.isArray(model.systems) ? model.systems : [],
    lastAction: String(model.lastAction ?? model.last_action ?? "No recent activity"),
    lastActionTime: String(model.lastActionTime ?? model.last_action_time ?? "recently"),
  }
}

async function loadKnowledgeDocCounts(
  supabase: ReturnType<typeof createSupabaseRouteClient>,
  orgId: string,
  agentIds: string[],
): Promise<Map<string, number>> {
  const counts = new Map<string, number>()
  if (agentIds.length === 0) return counts

  for (const agentId of agentIds) {
    counts.set(agentId, 0)
  }

  const { data: sources } = await supabase
    .from("rag_sources")
    .select("id, agent_id")
    .eq("org_id", orgId)
    .in("agent_id", agentIds)

  const sourceIds: string[] = []
  const sourcesByAgent = new Map<string, string[]>()
  for (const source of sources ?? []) {
    const agentId = String((source as { agent_id?: string }).agent_id ?? "")
    const sourceId = String((source as { id?: string }).id ?? "")
    if (!agentId || !sourceId) continue
    sourceIds.push(sourceId)
    const bucket = sourcesByAgent.get(agentId) ?? []
    bucket.push(sourceId)
    sourcesByAgent.set(agentId, bucket)
  }

  const docsBySource = new Map<string, number>()
  if (sourceIds.length > 0) {
    const { data: documents } = await supabase
      .from("rag_documents")
      .select("source_id")
      .in("source_id", sourceIds)

    for (const document of documents ?? []) {
      const sourceId = String((document as { source_id?: string }).source_id ?? "")
      if (!sourceId) continue
      docsBySource.set(sourceId, (docsBySource.get(sourceId) ?? 0) + 1)
    }
  }

  for (const [agentId, agentSources] of sourcesByAgent.entries()) {
    const ragCount = agentSources.reduce((total, sourceId) => total + (docsBySource.get(sourceId) ?? 0), 0)
    counts.set(agentId, (counts.get(agentId) ?? 0) + ragCount)
  }

  const { data: instructions } = await supabase
    .from("custom_instructions")
    .select("agent_id")
    .eq("org_id", orgId)
    .eq("is_active", true)
    .in("agent_id", agentIds)

  for (const instruction of instructions ?? []) {
    const agentId = String((instruction as { agent_id?: string }).agent_id ?? "")
    if (!agentId) continue
    counts.set(agentId, (counts.get(agentId) ?? 0) + 1)
  }

  return counts
}

export async function GET(request: NextRequest) {
  try {
    const debugEnabled = isDebugRequest(request.nextUrl.searchParams)
    const authMode = getRouteClientAuthMode(request)
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const diagnostics = await getOrgCountDiagnostics(supabase, "agents", orgId)
    const { data, error } = await supabase
      .from("agents")
      .select("*")
      .eq("org_id", orgId)
      .order("created_at", { ascending: false })

    if (error) {
      return NextResponse.json(
        {
          error: error.message,
          agents: [],
          operators: [],
          ...(debugEnabled
            ? {
                _debug: {
                  resolvedOrgId: orgId,
                  table: "agents",
                  ...diagnostics,
                  queryError: error.message,
                  authMode,
                },
              }
            : {}),
        },
        { status: 500 }
      )
    }

    const agentRows = data ?? []
    const agentIds = agentRows
      .map((row) => String((row as { id?: string }).id ?? ""))
      .filter((agentId) => agentId.length > 0)
    const knowledgeCounts = await loadKnowledgeDocCounts(supabase, orgId, agentIds)
    const agents = agentRows.map((row) =>
      mapAgentRow(row as Record<string, unknown>, knowledgeCounts.get(String((row as { id?: string }).id ?? "")) ?? 0),
    )

    return NextResponse.json({
      agents,
      operators: agents,
      ...(debugEnabled
        ? {
            _debug: {
              resolvedOrgId: orgId,
              table: "agents",
              ...diagnostics,
              queryError: null,
              authMode,
            },
          }
        : {}),
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error", agents: [], operators: [] },
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

    const permissions = Array.isArray(snake.permissions)
      ? snake.permissions
      : Array.isArray(snake.systems)
        ? snake.systems
        : []

    const insertPayload = {
      org_id: orgId,
      name: String(snake.name ?? "New Agent"),
      purpose: (snake.purpose as string | undefined) ?? null,
      role: (snake.role as string | undefined) ?? String(snake.name ?? "New Agent"),
      model: (snake.model as string | undefined) ?? "auto",
      department: (snake.department as string | undefined) ?? "Operations",
      description:
        (snake.description as string | undefined) ??
        (snake.purpose as string | undefined) ??
        null,
      personality:
        snake.personality && typeof snake.personality === "object"
          ? snake.personality
          : {
              color: "blue",
              gradient: "from-blue-500 to-indigo-500",
              glow: "shadow-blue-500/30",
            },
      stats:
        snake.stats && typeof snake.stats === "object"
          ? snake.stats
          : {
              tasksToday: 0,
              successRate: 100,
              avgResponseTime: "-",
              workflowsUsing: 0,
            },
      capabilities: Array.isArray(snake.capabilities) ? snake.capabilities : [],
      systems: permissions,
      guardrails: Array.isArray(snake.guardrails) ? snake.guardrails : [],
      status: "active",
      last_action:
        (snake.last_action as string | undefined) ??
        (snake.lastAction as string | undefined) ??
        "Created",
      last_action_time: new Date().toISOString(),
      created_by: userData.user?.id ?? null,
    }

    const { data, error } = await supabase
      .from("agents")
      .insert(insertPayload)
      .select("*")
      .single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ agent: mapAgentRow(data as Record<string, unknown>) }, { status: 201 })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
