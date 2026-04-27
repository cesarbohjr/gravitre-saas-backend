import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { ensureDemoDataForOrg } from "@/lib/supabase/demo-bootstrap"

type ConnectorStatus = "connected" | "disconnected" | "error" | "syncing"
type ConnectorEnvironment = "production" | "staging"
type ConnectorAuthType = "oauth" | "apiKey" | "webhook"

function normalizeStatus(value: unknown): ConnectorStatus {
  const status = String(value ?? "disconnected")
  if (status === "connected" || status === "error" || status === "syncing") return status
  return "disconnected"
}

function normalizeEnvironment(value: unknown): ConnectorEnvironment {
  return String(value ?? "production") === "staging" ? "staging" : "production"
}

function normalizeAuthType(value: unknown): ConnectorAuthType | undefined {
  const authType = String(value ?? "")
  if (authType === "oauth" || authType === "apiKey" || authType === "webhook") return authType
  return undefined
}

function toRelativeTimestamp(value: unknown): string {
  if (!value) return "Never"
  const date = new Date(String(value))
  if (Number.isNaN(date.getTime())) return "Never"

  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000))
  if (seconds < 60) return "Just now"
  if (seconds < 3600) return `${Math.floor(seconds / 60)} minutes ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} hours ago`
  return `${Math.floor(seconds / 86400)} days ago`
}

function mapConnectorRow(row: Record<string, unknown>) {
  return {
    id: String(row.id),
    name: String(row.name ?? row.system_key ?? "connector"),
    type: String(row.type ?? "Custom"),
    status: normalizeStatus(row.status),
    environment: normalizeEnvironment(row.environment),
    lastSync: toRelativeTimestamp(row.last_sync),
    health: Number(row.health ?? 0),
    description: String(row.description ?? ""),
    dataFlowRate: row.data_flow_rate ? String(row.data_flow_rate) : undefined,
    requestsToday: Number(row.requests_today ?? 0),
    latency: Number(row.latency ?? 0),
    category: row.category ? String(row.category) : undefined,
    authType: normalizeAuthType(row.auth_type),
    usedByWorkflows: Number(row.used_by_workflows ?? 0),
    triggeredByAgents: Number(row.triggered_by_agents ?? 0),
    config: row.config && typeof row.config === "object" ? row.config : {},
  }
}

function mapConnectedSystemFallback(row: Record<string, unknown>) {
  const config = row.config && typeof row.config === "object" ? (row.config as Record<string, unknown>) : {}
  return {
    id: String(row.id),
    name: String(row.system_key ?? row.name ?? "connector"),
    type: String(row.name ?? row.type ?? "Custom"),
    status: normalizeStatus(row.status),
    environment: normalizeEnvironment(config.environment),
    lastSync: toRelativeTimestamp(row.last_synced_at),
    health: Number(config.health ?? (row.status === "connected" ? 100 : 0)),
    description: String(config.description ?? ""),
    dataFlowRate: config.dataFlowRate ? String(config.dataFlowRate) : undefined,
    requestsToday: Number(config.requestsToday ?? 0),
    latency: Number(config.latency ?? 0),
    category: config.category ? String(config.category) : undefined,
    authType: normalizeAuthType(config.authType),
    usedByWorkflows: Number(config.usedByWorkflows ?? 0),
    triggeredByAgents: Number(config.triggeredByAgents ?? 0),
    config,
  }
}

function isMissingRelationError(message: string | undefined) {
  const value = String(message ?? "").toLowerCase()
  return value.includes("does not exist") || value.includes("relation")
}

export async function GET(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    await ensureDemoDataForOrg(supabase, orgId)

    const { data, error } = await supabase
      .from("connectors")
      .select("*")
      .eq("org_id", orgId)
      .order("created_at", { ascending: false })

    if (error) {
      if (!isMissingRelationError(error.message)) {
        return NextResponse.json({ error: error.message }, { status: 500 })
      }

      const { data: fallbackSystems, error: fallbackError } = await supabase
        .from("connected_systems")
        .select("*")
        .eq("org_id", orgId)
        .order("created_at", { ascending: false })

      if (fallbackError) {
        return NextResponse.json({ error: fallbackError.message }, { status: 500 })
      }

      return NextResponse.json({
        connectors: (fallbackSystems ?? []).map((row) => mapConnectedSystemFallback(row as Record<string, unknown>)),
      })
    }

    return NextResponse.json({
      connectors: (data ?? []).map((row) => mapConnectorRow(row as Record<string, unknown>)),
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

    const body = (await request.json().catch(() => ({}))) as Record<string, unknown>
    const now = new Date().toISOString()

    const insertPayload = {
      org_id: orgId,
      name: String(body.name ?? "new-connector").trim(),
      type: String(body.type ?? "Custom").trim(),
      status: normalizeStatus(body.status ?? "connected"),
      environment: normalizeEnvironment(body.environment),
      last_sync: now,
      health: Number(body.health ?? 100),
      description: body.description ? String(body.description) : null,
      data_flow_rate: body.dataFlowRate ? String(body.dataFlowRate) : null,
      requests_today: Number(body.requestsToday ?? 0),
      latency: Number(body.latency ?? 0),
      category: body.category ? String(body.category) : null,
      auth_type: normalizeAuthType(body.authType) ?? null,
      used_by_workflows: Number(body.usedByWorkflows ?? 0),
      triggered_by_agents: Number(body.triggeredByAgents ?? 0),
      config: body.config && typeof body.config === "object" ? body.config : {},
    }

    const { data, error } = await supabase.from("connectors").insert(insertPayload).select("*").single()
    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ connector: mapConnectorRow(data as Record<string, unknown>) }, { status: 201 })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
