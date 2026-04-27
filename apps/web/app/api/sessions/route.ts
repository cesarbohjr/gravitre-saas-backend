import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { ensureDemoDataForOrg } from "@/lib/supabase/demo-bootstrap"

type RecentActivityItem = {
  id: string
  type: string
  timestamp: string
  agentId?: string | null
  workflowId?: string | null
}

function toIsoTimestamp(value: string | null | undefined): string {
  if (!value) return new Date().toISOString()
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? new Date().toISOString() : date.toISOString()
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

    const [{ data: activeRuns, error: activeRunsError }, { data: recentRuns, error: recentRunsError }, { data: recentApprovals, error: recentApprovalsError }] =
      await Promise.all([
        supabase
          .from("runs")
          .select("id, workflow_id, approval_status, status, metadata")
          .eq("org_id", orgId)
          .or("status.in.(running,pending),approval_status.eq.pending")
          .limit(200),
        supabase
          .from("runs")
          .select("id, workflow_id, status, approval_status, metadata, created_at, updated_at")
          .eq("org_id", orgId)
          .order("updated_at", { ascending: false })
          .limit(20),
        supabase
          .from("approvals")
          .select("id, run_id, status, requested_at, reviewed_at, created_at")
          .eq("org_id", orgId)
          .order("requested_at", { ascending: false })
          .limit(20),
      ])

    if (activeRunsError || recentRunsError || recentApprovalsError) {
      const message = activeRunsError?.message ?? recentRunsError?.message ?? recentApprovalsError?.message
      return NextResponse.json({ error: message ?? "Failed to load sessions" }, { status: 500 })
    }

    const runActivities: RecentActivityItem[] = (recentRuns ?? []).map((run) => {
      const metadata = (run.metadata ?? {}) as Record<string, unknown>
      return {
        id: String(run.id),
        type: "run",
        timestamp: toIsoTimestamp(String(run.updated_at ?? run.created_at ?? "")),
        workflowId: run.workflow_id ? String(run.workflow_id) : null,
        agentId: metadata.agent_id ? String(metadata.agent_id) : null,
      }
    })

    const approvalActivities: RecentActivityItem[] = (recentApprovals ?? []).map((approval) => ({
      id: String(approval.id),
      type: "approval",
      timestamp: toIsoTimestamp(String(approval.reviewed_at ?? approval.requested_at ?? approval.created_at ?? "")),
      workflowId: approval.run_id ? String(approval.run_id) : null,
      agentId: null,
    }))

    const recentActivity = [...runActivities, ...approvalActivities]
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .slice(0, 25)

    const payload = {
      activeSessions: (activeRuns ?? []).length,
      recentActivity,
      // Backward-compatible fields for clients that still expect a list.
      sessions: recentActivity,
    }

    return NextResponse.json(payload)
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

    const body = await request.json().catch(() => ({}))
    const title = String(body?.title ?? "Operator Session").trim() || "Operator Session"
    const contextEntityType = body?.context?.entityType ? String(body.context.entityType) : null
    const contextEntityId = body?.context?.entityId ? String(body.context.entityId) : null

    const insertPayload: Record<string, unknown> = {
      org_id: orgId,
      title,
      status: "active",
      context_entity_type: contextEntityType,
      context_entity_id: contextEntityId,
    }

    const { data, error } = await supabase
      .from("sessions")
      .insert(insertPayload)
      .select("id, org_id, title, status, context_entity_type, context_entity_id, created_at")
      .single()

    if (error) {
      if (isMissingRelationError(error.message)) {
        const fallbackSession = {
          id: `session-${crypto.randomUUID()}`,
          orgId,
          title,
          status: "active",
          contextEntityType,
          contextEntityId,
          createdAt: new Date().toISOString(),
        }
        return NextResponse.json({ session: fallbackSession, persisted: false }, { status: 201 })
      }

      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json(
      {
        session: {
          id: data.id,
          orgId: data.org_id,
          title: data.title,
          status: data.status,
          contextEntityType: data.context_entity_type,
          contextEntityId: data.context_entity_id,
          createdAt: data.created_at,
        },
        persisted: true,
      },
      { status: 201 }
    )
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
