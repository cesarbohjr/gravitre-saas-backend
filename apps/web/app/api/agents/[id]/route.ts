import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, createSupabaseServiceRoleClient, resolveOrgId } from "@/lib/supabase/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
import {
  inferAgentDepartment,
  inferAgentPersonality,
  mapOperatorStatusToUi,
  normalizeAgentDepartment,
} from "@/lib/agent-display"
import {
  isAgentAvatarColorId,
  isAgentIconId,
  personalityFromAvatarColor,
  type AgentAvatarColorId,
} from "@/lib/agent-identity"
import { syncOperatorMirror } from "@/lib/agent-operator-mirror"
import { readReferenceFoldersFromRecord } from "@/lib/agent-reference-folders"
import { snakeToCamel, camelToSnake } from "@/lib/supabase/transforms"

interface RouteParams {
  params: Promise<{ id: string }>
}

function mapAgentRow(input: Record<string, unknown>) {
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
    icon: isAgentIconId(String(model.icon ?? "")) ? String(model.icon) : null,
    avatarColor: isAgentAvatarColorId(String(model.avatarColor ?? model.avatar_color ?? ""))
      ? String(model.avatarColor ?? model.avatar_color)
      : null,
    avatarUrl: typeof model.avatarUrl === "string"
      ? model.avatarUrl
      : typeof model.avatar_url === "string"
        ? model.avatar_url
        : null,
    knowledgeDocCount: 0,
    personality: {
      color: String(personality.color ?? inferAgentPersonality(department).color),
      gradient: String(personality.gradient ?? inferAgentPersonality(department).gradient),
      glow: String(personality.glow ?? inferAgentPersonality(department).glow),
    },
    stats: (() => {
      const tasksToday = Number(stats.tasksToday ?? stats.tasks_today ?? 0)
      const rawRate = stats.successRate ?? stats.success_rate
      const hasRate = rawRate !== undefined && rawRate !== null && rawRate !== ""
      const parsed = hasRate ? Number(rawRate) : null
      const successRate =
        tasksToday <= 0 && !hasRate
          ? null
          : parsed !== null && Number.isFinite(parsed)
            ? parsed
            : null
      return {
        tasksToday,
        successRate,
        successRateSource:
          successRate == null ? ("insufficient_data" as const) : ("stored_column" as const),
        avgResponseTime: String(stats.avgResponseTime ?? stats.avg_response_time ?? "-"),
        workflowsUsing: Number(stats.workflowsUsing ?? stats.workflows_using ?? 0),
        knowledgeDocCount: 0,
      }
    })(),
    capabilities: Array.isArray(model.capabilities) ? model.capabilities : [],
    permissions: Array.isArray(model.systems) ? model.systems : [],
    referenceFolders: readReferenceFoldersFromRecord(model),
    lastAction: String(model.lastAction ?? model.last_action ?? "No recent activity"),
    lastActionTime: String(model.lastActionTime ?? model.last_action_time ?? "recently"),
    recentTasks: [],
    createdAt: String(model.createdAt ?? model.created_at ?? ""),
  }
}

function mapOperatorRow(input: Record<string, unknown>) {
  const name = String(input.name ?? "Agent")
  const role = String(input.role ?? name)
  const department = inferAgentDepartment(name, String(input.description ?? ""), role)
  const personality = inferAgentPersonality(department)
  const totalRuns = Number(input.total_runs ?? 0)
  const hasRate = input.success_rate !== undefined && input.success_rate !== null && input.success_rate !== ""
  const parsedRate = hasRate ? Number(input.success_rate) : null
  const successRate =
    totalRuns <= 0 && !hasRate
      ? null
      : parsedRate !== null && Number.isFinite(parsedRate)
        ? parsedRate
        : null
  const icon = isAgentIconId(String(input.icon ?? "")) ? String(input.icon) : null
  const avatarColor = isAgentAvatarColorId(String(input.avatar_color ?? input.avatarColor ?? ""))
    ? String(input.avatar_color ?? input.avatarColor)
    : null

  return {
    id: String(input.id),
    name,
    role,
    department,
    description: String(input.description ?? "AI teammate"),
    status: mapOperatorStatusToUi(String(input.status ?? "draft")),
    model: "auto",
    icon,
    avatarColor,
    avatarUrl: typeof input.avatar_url === "string"
      ? input.avatar_url
      : typeof input.avatarUrl === "string"
        ? input.avatarUrl
        : null,
    knowledgeDocCount: 0,
    personality,
    stats: {
      tasksToday: totalRuns,
      successRate,
      successRateSource:
        successRate == null ? ("insufficient_data" as const) : ("stored_column" as const),
      avgResponseTime: "-",
      workflowsUsing: 0,
      knowledgeDocCount: 0,
    },
    capabilities: Array.isArray(input.capabilities) ? input.capabilities : [],
    permissions: [],
    lastAction: "No recent activity",
    lastActionTime: "recently",
    recentTasks: [],
    createdAt: String(input.created_at ?? ""),
  }
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  const { id } = await params
  const supabase = createSupabaseRouteClient(request)
  const orgId = await resolveOrgId(supabase, request)
  if (!orgId) {
    return NextResponse.json({ error: "Organization context required" }, { status: 403 })
  }

  const { data: agentRow, error: agentError } = await supabase
    .from("agents")
    .select("*")
    .eq("org_id", orgId)
    .eq("id", id)
    .maybeSingle()

  if (agentError) {
    return NextResponse.json({ error: agentError.message }, { status: 500 })
  }

  if (agentRow) {
    return NextResponse.json({ agent: mapAgentRow(agentRow as Record<string, unknown>) })
  }

  const { data: operatorRow } = await supabase
    .from("operators")
    .select("id, org_id, name, description, status, role, capabilities, total_runs, success_rate, created_at")
    .eq("org_id", orgId)
    .eq("id", id)
    .maybeSingle()

  if (operatorRow) {
    return NextResponse.json({ agent: mapOperatorRow(operatorRow as Record<string, unknown>) })
  }

  const serviceClient = createSupabaseServiceRoleClient()
  if (serviceClient) {
    const { data: serviceAgentRow } = await serviceClient
      .from("agents")
      .select("*")
      .eq("org_id", orgId)
      .eq("id", id)
      .maybeSingle()
    if (serviceAgentRow) {
      return NextResponse.json({ agent: mapAgentRow(serviceAgentRow as Record<string, unknown>) })
    }

    const { data: serviceOperatorRow } = await serviceClient
      .from("operators")
      .select("id, org_id, name, description, status, role, capabilities, total_runs, success_rate, created_at")
      .eq("org_id", orgId)
      .eq("id", id)
      .maybeSingle()
    if (serviceOperatorRow) {
      return NextResponse.json({ agent: mapOperatorRow(serviceOperatorRow as Record<string, unknown>) })
    }
  }

  return proxyToFastApi(request, `/api/agents/${id}`)
}

export async function PATCH(request: NextRequest, { params }: RouteParams) {
  const { id } = await params
  const supabase = createSupabaseRouteClient(request)
  const orgId = await resolveOrgId(supabase, request)
  if (!orgId) {
    return NextResponse.json({ error: "Organization context required" }, { status: 403 })
  }

  const body = await request.json().catch(() => ({}))
  const referenceFolders = (body as Record<string, unknown>).referenceFolders

  if (Array.isArray(referenceFolders)) {
    const { data: existing, error: loadError } = await supabase
      .from("agents")
      .select("*")
      .eq("org_id", orgId)
      .eq("id", id)
      .maybeSingle()

    if (loadError) {
      return NextResponse.json({ error: loadError.message }, { status: 500 })
    }
    if (!existing) {
      return proxyToFastApi(request, `/api/agents/${id}`)
    }

    const currentConfig =
      existing.config && typeof existing.config === "object"
        ? (existing.config as Record<string, unknown>)
        : {}

    const { data, error } = await supabase
      .from("agents")
      .update({
        config: {
          ...currentConfig,
          reference_folders: referenceFolders,
        },
        updated_at: new Date().toISOString(),
      })
      .eq("org_id", orgId)
      .eq("id", id)
      .select("*")
      .single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ agent: mapAgentRow(data as Record<string, unknown>) })
  }

  const snakeBody = camelToSnake(body as Record<string, unknown>)
  if (Array.isArray(snakeBody.reference_folders)) {
    const { data: existing, error: loadError } = await supabase
      .from("agents")
      .select("*")
      .eq("org_id", orgId)
      .eq("id", id)
      .maybeSingle()

    if (loadError) {
      return NextResponse.json({ error: loadError.message }, { status: 500 })
    }
    if (!existing) {
      return proxyToFastApi(request, `/api/agents/${id}`)
    }

    const currentConfig =
      existing.config && typeof existing.config === "object"
        ? (existing.config as Record<string, unknown>)
        : {}

    const { data, error } = await supabase
      .from("agents")
      .update({
        config: {
          ...currentConfig,
          reference_folders: snakeBody.reference_folders,
        },
        updated_at: new Date().toISOString(),
      })
      .eq("org_id", orgId)
      .eq("id", id)
      .select("*")
      .single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ agent: mapAgentRow(data as Record<string, unknown>) })
  }

  const identityKeys = ["name", "icon", "avatarColor", "avatar_color", "avatarUrl", "avatar_url", "personality", "description", "role", "department"]
  const bodyRecord = body as Record<string, unknown>
  const hasIdentityPatch = identityKeys.some((key) => key in bodyRecord)

  if (hasIdentityPatch) {
    const { data: existing, error: loadError } = await supabase
      .from("agents")
      .select("*")
      .eq("org_id", orgId)
      .eq("id", id)
      .maybeSingle()

    if (loadError) {
      return NextResponse.json({ error: loadError.message }, { status: 500 })
    }
    if (!existing) {
      return proxyToFastApi(request, `/api/agents/${id}`)
    }

    const snakeBody = camelToSnake(bodyRecord)
    const updatePayload: Record<string, unknown> = {
      updated_at: new Date().toISOString(),
    }

    if (typeof snakeBody.name === "string" && snakeBody.name.trim()) {
      updatePayload.name = snakeBody.name.trim()
    }
    if (typeof snakeBody.description === "string") {
      updatePayload.description = snakeBody.description
    }
    if (typeof snakeBody.role === "string") {
      updatePayload.role = snakeBody.role
    }
    if (typeof snakeBody.department === "string") {
      updatePayload.department = snakeBody.department
    }
    if (snakeBody.icon !== undefined) {
      if (snakeBody.icon !== null && !isAgentIconId(String(snakeBody.icon))) {
        return NextResponse.json({ error: "Invalid icon value" }, { status: 400 })
      }
      updatePayload.icon = snakeBody.icon
    }
    const incomingColor = snakeBody.avatar_color ?? snakeBody.avatarColor
    if (incomingColor !== undefined) {
      if (incomingColor !== null && !isAgentAvatarColorId(String(incomingColor))) {
        return NextResponse.json({ error: "Invalid avatarColor value" }, { status: 400 })
      }
      updatePayload.avatar_color = incomingColor
    }
    if (snakeBody.avatar_url !== undefined || snakeBody.avatarUrl !== undefined) {
      const incomingUrl = snakeBody.avatar_url ?? snakeBody.avatarUrl
      updatePayload.avatar_url = incomingUrl === null || incomingUrl === "" ? null : String(incomingUrl)
    }
    if (snakeBody.personality && typeof snakeBody.personality === "object") {
      updatePayload.personality = snakeBody.personality
    } else if (isAgentAvatarColorId(String(updatePayload.avatar_color ?? ""))) {
      updatePayload.personality = personalityFromAvatarColor(updatePayload.avatar_color as AgentAvatarColorId)
    }

    const { data, error } = await supabase
      .from("agents")
      .update(updatePayload)
      .eq("org_id", orgId)
      .eq("id", id)
      .select("*")
      .single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    const { data: userData } = await supabase.auth.getUser()
    await syncOperatorMirror(
      supabase,
      orgId,
      data as Record<string, unknown>,
      userData.user?.id ?? null,
    )

    return NextResponse.json({ agent: mapAgentRow(data as Record<string, unknown>) })
  }

  return proxyToFastApi(request, `/api/agents/${id}`)
}

export async function DELETE(request: NextRequest, { params }: RouteParams) {
  const { id } = await params
  return proxyToFastApi(request, `/api/agents/${id}`)
}
