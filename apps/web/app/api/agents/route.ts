import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, getRouteClientAuthMode, resolveOrgId } from "@/lib/supabase/server"
import { ensureDemoDataForOrg, getDemoRowsForOrg } from "@/lib/supabase/demo-bootstrap"
import { getOrgCountDiagnostics, isDebugRequest } from "@/lib/supabase/route-diagnostics"
import { camelToSnake, snakeToCamel } from "@/lib/supabase/transforms"

function mapAgentRow(input: Record<string, unknown>) {
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
    },
    capabilities: Array.isArray(model.capabilities) ? model.capabilities : [],
    permissions: Array.isArray(model.systems) ? model.systems : [],
    lastAction: String(model.lastAction ?? model.last_action ?? "No recent activity"),
    lastActionTime: String(model.lastActionTime ?? model.last_action_time ?? "recently"),
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
    await ensureDemoDataForOrg(supabase, orgId)
    const demoRows = getDemoRowsForOrg(orgId)

    const diagnostics = await getOrgCountDiagnostics(supabase, "agents", orgId)
    const { data, error } = await supabase
      .from("agents")
      .select("*")
      .eq("org_id", orgId)
      .order("created_at", { ascending: false })

    if (error) {
      const fallbackAgents = (demoRows?.agents ?? []).map((row) => mapAgentRow(row as Record<string, unknown>))

      return NextResponse.json(
        {
          ...(fallbackAgents.length > 0 ? { agents: fallbackAgents, operators: fallbackAgents } : { error: error.message }),
          ...(debugEnabled
            ? {
                _debug: {
                  resolvedOrgId: orgId,
                  table: "agents",
                  ...diagnostics,
                  queryError: error.message,
                  fallbackUsed: fallbackAgents.length > 0,
                  authMode,
                },
              }
            : {}),
        },
        { status: fallbackAgents.length > 0 ? 200 : 500 }
      )
    }

    const agents = (data ?? []).map((row) => mapAgentRow(row as Record<string, unknown>))

    if ((data ?? []).length === 0) {
      console.warn("Agents route returned empty result", {
        orgId,
        diagnostics,
        authMode,
      })
    }

    const safeAgents =
      agents.length > 0
        ? agents
        : (demoRows?.agents ?? []).map((row) => mapAgentRow(row as Record<string, unknown>))

    return NextResponse.json({
      agents: safeAgents,
      operators: safeAgents,
      ...(debugEnabled
        ? {
            _debug: {
              resolvedOrgId: orgId,
              table: "agents",
              ...diagnostics,
              queryError: null,
              fallbackUsed: agents.length === 0 && safeAgents.length > 0,
              authMode,
            },
          }
        : {}),
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
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
