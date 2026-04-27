import { NextRequest, NextResponse } from "next/server"
import { snakeToCamel } from "@/lib/supabase/transforms"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"

interface RouteParams {
  params: Promise<{ id: string }>
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  try {
    const { id } = await params
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const { data: goal, error: goalError } = await supabase
      .from("goals")
      .select("*")
      .eq("org_id", orgId)
      .eq("id", id)
      .single()
    if (goalError) {
      return NextResponse.json({ error: goalError.message }, { status: goalError.code === "PGRST116" ? 404 : 500 })
    }

    const { data: planRows } = await supabase
      .from("goal_plans")
      .select("*")
      .eq("org_id", orgId)
      .eq("goal_id", id)
      .order("created_at", { ascending: false })
      .limit(1)

    const { data: runs } = await supabase
      .from("runs")
      .select("*")
      .eq("org_id", orgId)
      .order("created_at", { ascending: false })
      .limit(8)

    const latestPlan = planRows?.[0]
    const proposedSteps = Array.isArray(latestPlan?.proposed_steps) ? latestPlan.proposed_steps : []
    const completedByStatus = String(goal.status) === "completed" ? 100 : 0
    const completedBySteps = proposedSteps.length > 0 ? Math.min(95, Math.round((proposedSteps.length - 1) * (100 / proposedSteps.length))) : 0
    const completionPercentage = Math.max(completedByStatus, completedBySteps)

    const milestoneStatus = proposedSteps.map((step, index) => ({
      id: (step as { id?: string }).id ?? `milestone-${index + 1}`,
      title: (step as { title?: string }).title ?? `Milestone ${index + 1}`,
      status: completionPercentage === 100 ? "completed" : index === 0 ? "in_progress" : "planned",
    }))

    const runHistory = (runs ?? []).map((row) => {
      const model = snakeToCamel<Record<string, unknown>>(row)
      return {
        id: model.id,
        status: model.status ?? "pending",
        startedAt: model.startedAt ?? null,
        completedAt: model.completedAt ?? null,
        durationMs: model.durationMs ?? null,
      }
    })

    const recentDeliverables = runHistory.slice(0, 3).map((run, idx) => ({
      id: `deliverable-${idx + 1}`,
      title: `Run ${String(run.id).slice(0, 8)} output`,
      status: run.status,
      completedAt: run.completedAt,
    }))

    return NextResponse.json({
      goal: snakeToCamel<Record<string, unknown>>(goal),
      completionPercentage,
      milestoneStatus,
      recentDeliverables,
      runHistory,
      successMetricTracking:
        (snakeToCamel<Record<string, unknown>>(goal).successMetrics as Record<string, unknown>) ?? {},
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
