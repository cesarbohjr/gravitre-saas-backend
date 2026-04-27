import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"

interface RouteParams {
  params: Promise<{ id: string }>
}

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0))
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  try {
    const { id } = await params
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const { data: agent, error: agentError } = await supabase
      .from("agents")
      .select("*")
      .eq("org_id", orgId)
      .eq("id", id)
      .single()
    if (agentError) {
      return NextResponse.json({ error: agentError.message }, { status: agentError.code === "PGRST116" ? 404 : 500 })
    }

    const { data: runs } = await supabase
      .from("runs")
      .select("id, status, approval_status, created_at")
      .eq("org_id", orgId)
      .order("created_at", { ascending: false })
      .limit(90)
    const { data: approvals } = await supabase
      .from("approvals")
      .select("id, status")
      .eq("org_id", orgId)
      .order("requested_at", { ascending: false })
      .limit(200)

    const totalRuns = runs?.length ?? 0
    const completed = (runs ?? []).filter((run) => run.status === "completed").length
    const failed = (runs ?? []).filter((run) => run.status === "failed").length
    const approvalsPending = (approvals ?? []).filter((item) => item.status === "pending").length
    const approvalsTotal = approvals?.length ?? 0
    const runOverrideRate = totalRuns > 0 ? ((runs ?? []).filter((run) => run.approval_status === "pending").length / totalRuns) * 100 : 0

    const config =
      agent.config && typeof agent.config === "object" ? (agent.config as Record<string, unknown>) : {}
    const fallbackTasks = Number(config.tasks_today ?? 0)
    const fallbackSuccessRate = Number(config.success_rate ?? 0)
    const weakAreas = failed > completed / 2
      ? ["error recovery", "retry strategy"]
      : approvalsPending > 0
      ? ["approval throughput"]
      : []

    const trendOverTime = (runs ?? [])
      .slice(0, 14)
      .reverse()
      .map((run) => ({
        timestamp: run.created_at,
        success: run.status === "completed",
      }))

    return NextResponse.json({
      tasksCompleted: completed || fallbackTasks,
      avgConfidence: clampPercent(fallbackSuccessRate || (completed / Math.max(totalRuns, 1)) * 100),
      overrideRate: clampPercent(runOverrideRate),
      errorRate: clampPercent(totalRuns > 0 ? (failed / totalRuns) * 100 : 0),
      weakAreas,
      trendOverTime,
      meta: {
        approvalsPending,
        approvalsTotal,
      },
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
