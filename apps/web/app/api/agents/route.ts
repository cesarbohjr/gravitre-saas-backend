import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, getRouteClientAuthMode, resolveOrgId } from "@/lib/supabase/server"
import { getOrgCountDiagnostics, isDebugRequest } from "@/lib/supabase/route-diagnostics"
import { camelToSnake, snakeToCamel } from "@/lib/supabase/transforms"
import {
  inferAgentDepartment,
  inferAgentPersonality,
  mapAgentStatusToOperator,
  mapOperatorStatusToUi,
  normalizeAgentDepartment,
} from "@/lib/agent-display"
import { readReferenceFoldersFromRecord } from "@/lib/agent-reference-folders"

function mapAgentRow(
  input: Record<string, unknown>,
  knowledgeDocCount = 0,
  recentTasks: Array<{ id: string; title: string; time: string; status: string }> = [],
) {
  const model = snakeToCamel<Record<string, unknown>>(input)
  const personality =
    model.personality && typeof model.personality === "object"
      ? (model.personality as Record<string, unknown>)
      : {}
  const stats = model.stats && typeof model.stats === "object" ? (model.stats as Record<string, unknown>) : {}
  const department = normalizeAgentDepartment(String(model.department ?? "Operations"))

  return {
    id: String(model.id),
    name: String(model.name ?? "Agent"),
    role: String(model.role ?? model.name ?? "AI Agent"),
    department,
    description: String(model.description ?? model.purpose ?? "AI teammate"),
    status: mapOperatorStatusToUi(String(model.status ?? "idle")),
    model: String(model.model ?? "auto"),
    knowledgeDocCount,
    personality: {
      color: String(personality.color ?? inferAgentPersonality(department).color),
      gradient: String(personality.gradient ?? inferAgentPersonality(department).gradient),
      glow: String(personality.glow ?? inferAgentPersonality(department).glow),
    },
    stats: {
      tasksToday: Number(stats.tasksToday ?? stats.tasks_today ?? 0),
      successRate: Number(stats.successRate ?? stats.success_rate ?? 100),
      avgResponseTime: String(stats.avgResponseTime ?? stats.avg_response_time ?? "-"),
      workflowsUsing: Number(stats.workflowsUsing ?? stats.workflows_using ?? 0),
      knowledgeDocCount,
    },
    capabilities: Array.isArray(model.capabilities) ? model.capabilities : [],
    permissions: Array.isArray(model.systems) ? model.systems : [],
    referenceFolders: readReferenceFoldersFromRecord(model),
    lastAction: String(model.lastAction ?? model.last_action ?? "No recent activity"),
    lastActionTime: String(model.lastActionTime ?? model.last_action_time ?? "recently"),
    recentTasks,
    createdAt: String(model.createdAt ?? model.created_at ?? ""),
  }
}

function mapOperatorRow(
  input: Record<string, unknown>,
  knowledgeDocCount = 0,
  recentTasks: Array<{ id: string; title: string; time: string; status: string }> = [],
) {
  const name = String(input.name ?? "Agent")
  const role = String(input.role ?? name)
  const department = inferAgentDepartment(name, String(input.description ?? ""), role)
  const personality = inferAgentPersonality(department)
  const successRate = Number(input.success_rate ?? 100)
  const totalRuns = Number(input.total_runs ?? 0)

  return {
    id: String(input.id),
    name,
    role,
    department,
    description: String(input.description ?? "AI teammate"),
    status: mapOperatorStatusToUi(String(input.status ?? "draft")),
    model: "auto",
    knowledgeDocCount,
    personality,
    stats: {
      tasksToday: totalRuns,
      successRate: Number.isFinite(successRate) ? successRate : 100,
      avgResponseTime: "-",
      workflowsUsing: 0,
      knowledgeDocCount,
    },
    capabilities: Array.isArray(input.capabilities) ? input.capabilities : [],
    permissions: [],
    lastAction: "No recent activity",
    lastActionTime: "recently",
    recentTasks,
    createdAt: String(input.created_at ?? ""),
  }
}

async function loadRecentTasksForAgents(
  supabase: ReturnType<typeof createSupabaseRouteClient>,
  orgId: string,
  agentIds: string[],
): Promise<Map<string, Array<{ id: string; title: string; time: string; status: string }>>> {
  const byAgent = new Map<string, Array<{ id: string; title: string; time: string; status: string }>>()
  for (const agentId of agentIds) {
    byAgent.set(agentId, [])
  }
  if (agentIds.length === 0) return byAgent

  const { data: jobs } = await supabase
    .from("agent_jobs")
    .select("id, status, payload, created_at, finished_at")
    .eq("org_id", orgId)
    .order("created_at", { ascending: false })
    .limit(120)

  for (const row of jobs ?? []) {
    const payload = ((row as { payload?: unknown }).payload ?? {}) as Record<string, unknown>
    const context =
      payload.context && typeof payload.context === "object"
        ? (payload.context as Record<string, unknown>)
        : {}
    const agentId = String(
      payload.agent_id ?? payload.agentId ?? context.agent_id ?? context.agentId ?? "",
    )
    if (!agentId || !byAgent.has(agentId)) continue

    const bucket = byAgent.get(agentId) ?? []
    if (bucket.length >= 3) continue

    const rawTitle = String(payload.task ?? "Agent task").trim() || "Agent task"
    bucket.push({
      id: String((row as { id?: string }).id ?? ""),
      title: rawTitle.length > 80 ? `${rawTitle.slice(0, 77)}…` : rawTitle,
      time: String(
        (row as { finished_at?: string }).finished_at ??
          (row as { created_at?: string }).created_at ??
          "",
      ),
      status: String((row as { status?: string }).status ?? "queued"),
    })
    byAgent.set(agentId, bucket)
  }

  return byAgent
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

async function syncOperatorMirror(
  supabase: ReturnType<typeof createSupabaseRouteClient>,
  orgId: string,
  agentRow: Record<string, unknown>,
  userId: string | null,
) {
  const agentId = String(agentRow.id ?? "")
  if (!agentId) return

  const operatorPayload: Record<string, unknown> = {
    id: agentId,
    org_id: orgId,
    name: String(agentRow.name ?? "Agent"),
    description: (agentRow.description as string | null | undefined) ?? (agentRow.purpose as string | null | undefined) ?? null,
    role: (agentRow.role as string | null | undefined) ?? String(agentRow.name ?? "Agent"),
    status: mapAgentStatusToOperator(String(agentRow.status ?? "active")),
    capabilities: Array.isArray(agentRow.capabilities) ? agentRow.capabilities : [],
    config: agentRow.config && typeof agentRow.config === "object" ? agentRow.config : {},
    updated_at: new Date().toISOString(),
  }
  if (userId) {
    operatorPayload.created_by = userId
  }

  const { error } = await supabase.from("operators").upsert(operatorPayload, { onConflict: "id" })
  if (error) {
    console.warn("[agents] operator mirror upsert failed:", error.message)
  }
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
    const mergedIds = new Set<string>()
    const mergedRows: Record<string, unknown>[] = []

    for (const row of agentRows) {
      const id = String((row as { id?: string }).id ?? "")
      if (!id || mergedIds.has(id)) continue
      mergedIds.add(id)
      mergedRows.push(row as Record<string, unknown>)
    }

    const { data: operatorRows, error: operatorError } = await supabase
      .from("operators")
      .select("id, org_id, name, description, status, role, capabilities, total_runs, success_rate, created_at")
      .eq("org_id", orgId)
      .order("created_at", { ascending: false })

    if (operatorError) {
      console.warn("[agents] operators list failed:", operatorError.message)
    } else {
      for (const row of operatorRows ?? []) {
        const id = String((row as { id?: string }).id ?? "")
        if (!id || mergedIds.has(id)) continue
        mergedIds.add(id)
        mergedRows.push(row as Record<string, unknown>)
      }
    }

    const knowledgeCounts = await loadKnowledgeDocCounts(supabase, orgId, Array.from(mergedIds))
    const recentTasksByAgent = await loadRecentTasksForAgents(supabase, orgId, Array.from(mergedIds))
    const agents = mergedRows
      .map((row) => {
        const id = String(row.id ?? "")
        const knowledgeDocCount = knowledgeCounts.get(id) ?? 0
        const recentTasks = recentTasksByAgent.get(id) ?? []
        if ("purpose" in row || "personality" in row || "stats" in row) {
          return mapAgentRow(row, knowledgeDocCount, recentTasks)
        }
        return mapOperatorRow(row, knowledgeDocCount, recentTasks)
      })
      .sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)))

    return NextResponse.json({
      agents,
      operators: agents,
      ...(debugEnabled
        ? {
            _debug: {
              resolvedOrgId: orgId,
              table: "agents+operators",
              ...diagnostics,
              queryError: null,
              authMode,
              mergedCount: agents.length,
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

    const name = String(snake.name ?? "New Agent").trim()
    const purpose = (snake.purpose as string | undefined) ?? null
    const role = (snake.role as string | undefined) ?? name
    const department =
      (snake.department as string | undefined) ??
      inferAgentDepartment(name, purpose, role)

    const referenceFolders = Array.isArray(body.referenceFolders)
      ? body.referenceFolders
      : Array.isArray(snake.reference_folders)
        ? snake.reference_folders
        : []
    const existingConfig =
      snake.config && typeof snake.config === "object"
        ? (snake.config as Record<string, unknown>)
        : {}

    const insertPayload = {
      org_id: orgId,
      name,
      purpose,
      role,
      model: (snake.model as string | undefined) ?? "auto",
      department,
      description: (snake.description as string | undefined) ?? purpose ?? null,
      personality:
        snake.personality && typeof snake.personality === "object"
          ? snake.personality
          : inferAgentPersonality(normalizeAgentDepartment(department)),
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
      config: {
        ...existingConfig,
        reference_folders: referenceFolders,
      },
      status: String(snake.status ?? "active"),
      last_action:
        (snake.last_action as string | undefined) ??
        (snake.lastAction as string | undefined) ??
        "Created",
      last_action_time: new Date().toISOString(),
      created_by: userData.user?.id ?? null,
    }

    const { data, error } = await supabase.from("agents").insert(insertPayload).select("*").single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    await syncOperatorMirror(
      supabase,
      orgId,
      data as Record<string, unknown>,
      userData.user?.id ?? null,
    )

    const mapped = mapAgentRow(data as Record<string, unknown>)
    return NextResponse.json({ agent: mapped, id: mapped.id, agentId: mapped.id }, { status: 201 })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
