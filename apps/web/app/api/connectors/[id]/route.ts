import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"

type ConnectorStatus = "connected" | "disconnected" | "error" | "syncing"
type ConnectorEnvironment = "production" | "staging"
type ConnectorAuthType = "oauth" | "apiKey" | "webhook"

interface RouteParams {
  params: Promise<{ id: string }>
}

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
    name: String(row.name ?? "connector"),
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

function isNotFoundError(code: string | undefined) {
  return code === "PGRST116"
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  try {
    const { id } = await params
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const { data, error } = await supabase.from("connectors").select("*").eq("org_id", orgId).eq("id", id).single()
    if (error) {
      return NextResponse.json({ error: error.message }, { status: isNotFoundError(error.code) ? 404 : 500 })
    }

    return NextResponse.json({ connector: mapConnectorRow(data as Record<string, unknown>) })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}

export async function PATCH(request: NextRequest, { params }: RouteParams) {
  try {
    const { id } = await params
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const body = (await request.json().catch(() => ({}))) as Record<string, unknown>
    const updatePayload: Record<string, unknown> = {}

    if ("name" in body) updatePayload.name = String(body.name ?? "").trim()
    if ("type" in body) updatePayload.type = String(body.type ?? "").trim()
    if ("status" in body) updatePayload.status = normalizeStatus(body.status)
    if ("environment" in body) updatePayload.environment = normalizeEnvironment(body.environment)
    if ("health" in body) updatePayload.health = Number(body.health ?? 0)
    if ("description" in body) updatePayload.description = body.description ? String(body.description) : null
    if ("dataFlowRate" in body) updatePayload.data_flow_rate = body.dataFlowRate ? String(body.dataFlowRate) : null
    if ("requestsToday" in body) updatePayload.requests_today = Number(body.requestsToday ?? 0)
    if ("latency" in body) updatePayload.latency = Number(body.latency ?? 0)
    if ("category" in body) updatePayload.category = body.category ? String(body.category) : null
    if ("authType" in body) updatePayload.auth_type = normalizeAuthType(body.authType) ?? null
    if ("usedByWorkflows" in body) updatePayload.used_by_workflows = Number(body.usedByWorkflows ?? 0)
    if ("triggeredByAgents" in body) updatePayload.triggered_by_agents = Number(body.triggeredByAgents ?? 0)
    if ("config" in body) updatePayload.config = body.config && typeof body.config === "object" ? body.config : {}
    if ("lastSync" in body) {
      updatePayload.last_sync = body.lastSync ? new Date(String(body.lastSync)).toISOString() : null
    }

    const { data, error } = await supabase
      .from("connectors")
      .update(updatePayload)
      .eq("org_id", orgId)
      .eq("id", id)
      .select("*")
      .single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: isNotFoundError(error.code) ? 404 : 500 })
    }

    return NextResponse.json({ connector: mapConnectorRow(data as Record<string, unknown>) })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}

export async function DELETE(request: NextRequest, { params }: RouteParams) {
  try {
    const { id } = await params
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const { error } = await supabase.from("connectors").delete().eq("org_id", orgId).eq("id", id)
    if (error) {
      return NextResponse.json({ error: error.message }, { status: isNotFoundError(error.code) ? 404 : 500 })
    }

    return NextResponse.json({ success: true })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
