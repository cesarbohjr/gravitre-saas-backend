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
import {
  normalizeAgentResponseStyle,
  readResponseStyleFromConfig,
} from "@/lib/agent-response-style"
import {
  assertCanConfigureVoice,
  voiceProfileIsConfigured,
} from "@/lib/voice-configure-gate"

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
    guardrails: Array.isArray(model.guardrails) ? model.guardrails : [],
    referenceFolders: readReferenceFoldersFromRecord(model),
    responseStyle: readResponseStyleFromConfig(model.config),
    voiceProfile:
      model.voiceProfile && typeof model.voiceProfile === "object"
        ? model.voiceProfile
        : model.voice_profile && typeof model.voice_profile === "object"
          ? model.voice_profile
          : {},
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
    guardrails: [],
    responseStyle: readResponseStyleFromConfig(null),
    voiceProfile: {},
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
  const bodyRecord = body as Record<string, unknown>
  const snakeBody = camelToSnake(bodyRecord)

  const handledKeys = [
    "name",
    "icon",
    "avatarColor",
    "avatar_color",
    "avatarUrl",
    "avatar_url",
    "personality",
    "description",
    "role",
    "department",
    "model",
    "voiceProfile",
    "voice_profile",
    "capabilities",
    "systems",
    "permissions",
    "guardrails",
    "responseStyle",
    "response_style",
    "referenceFolders",
    "reference_folders",
  ]
  const hasHandledPatch = handledKeys.some((key) => key in bodyRecord || key in snakeBody)
  if (!hasHandledPatch) {
    return proxyToFastApi(request, `/api/agents/${id}`)
  }

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
  if (typeof snakeBody.model === "string" && snakeBody.model.trim()) {
    updatePayload.model = snakeBody.model.trim()
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

  if (Array.isArray(bodyRecord.capabilities) || Array.isArray(snakeBody.capabilities)) {
    updatePayload.capabilities = Array.isArray(bodyRecord.capabilities)
      ? bodyRecord.capabilities
      : snakeBody.capabilities
  }
  if (
    Array.isArray(bodyRecord.systems) ||
    Array.isArray(snakeBody.systems) ||
    Array.isArray(bodyRecord.permissions) ||
    Array.isArray(snakeBody.permissions)
  ) {
    updatePayload.systems =
      (Array.isArray(bodyRecord.systems) && bodyRecord.systems) ||
      (Array.isArray(snakeBody.systems) && snakeBody.systems) ||
      (Array.isArray(bodyRecord.permissions) && bodyRecord.permissions) ||
      snakeBody.permissions
  }
  if (Array.isArray(bodyRecord.guardrails) || Array.isArray(snakeBody.guardrails)) {
    updatePayload.guardrails = Array.isArray(bodyRecord.guardrails)
      ? bodyRecord.guardrails
      : snakeBody.guardrails
  }

  const voiceProfile =
    (bodyRecord.voiceProfile && typeof bodyRecord.voiceProfile === "object"
      ? bodyRecord.voiceProfile
      : null) ??
    (snakeBody.voice_profile && typeof snakeBody.voice_profile === "object"
      ? snakeBody.voice_profile
      : null)
  if (voiceProfile) {
    if (voiceProfileIsConfigured(voiceProfile)) {
      const { data: userData } = await supabase.auth.getUser()
      const gate = await assertCanConfigureVoice(
        supabase,
        orgId,
        userData.user?.id ?? null,
      )
      if (!gate.ok) {
        return NextResponse.json(
          { error: gate.error, reason: gate.reason, action: "voice_configure" },
          { status: gate.status },
        )
      }
    }
    updatePayload.voice_profile = voiceProfile
  }

  const currentConfig =
    existing.config && typeof existing.config === "object"
      ? (existing.config as Record<string, unknown>)
      : {}
  let nextConfig: Record<string, unknown> | null = null

  const referenceFolders =
    (Array.isArray(bodyRecord.referenceFolders) && bodyRecord.referenceFolders) ||
    (Array.isArray(snakeBody.reference_folders) && snakeBody.reference_folders) ||
    null
  if (referenceFolders) {
    nextConfig = {
      ...(nextConfig ?? currentConfig),
      reference_folders: referenceFolders,
    }
  }

  if (
    typeof bodyRecord.responseStyle === "string" ||
    typeof snakeBody.response_style === "string"
  ) {
    const style = normalizeAgentResponseStyle(
      typeof bodyRecord.responseStyle === "string"
        ? bodyRecord.responseStyle
        : String(snakeBody.response_style),
    )
    nextConfig = {
      ...(nextConfig ?? currentConfig),
      response_style: style,
    }
  }

  if (nextConfig) {
    updatePayload.config = nextConfig
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

export async function DELETE(request: NextRequest, { params }: RouteParams) {
  const { id } = await params
  return proxyToFastApi(request, `/api/agents/${id}`)
}
