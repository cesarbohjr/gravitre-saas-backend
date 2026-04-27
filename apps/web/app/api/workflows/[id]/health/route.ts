import { NextRequest, NextResponse } from "next/server"
import { snakeToCamel } from "@/lib/supabase/transforms"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"

interface RouteParams {
  params: Promise<{ id: string }>
}

function clampScore(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)))
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  try {
    const { id } = await params
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString()
    const { data: snapshots } = await supabase
      .from("workflow_health_snapshots")
      .select("*")
      .eq("org_id", orgId)
      .eq("workflow_id", id)
      .gte("recorded_at", sevenDaysAgo)
      .order("recorded_at", { ascending: true })

    const defaultDimensions = {
      reliability: 0,
      speed: 0,
      costEfficiency: 0,
      overrideRate: 0,
      goalCompletion: 0,
      decisionAccuracy: 0,
    }

    if (snapshots && snapshots.length > 0) {
      const latest = snapshots[snapshots.length - 1]
      const latestModel = snakeToCamel<Record<string, unknown>>(latest)
      const dimensions = {
        ...defaultDimensions,
        ...((latestModel.dimensions as Record<string, number> | undefined) ?? {}),
      }
      const trendData = snapshots.map((row) => {
        const model = snakeToCamel<Record<string, unknown>>(row)
        return {
          recordedAt: model.recordedAt,
          healthScore: Number(model.score ?? 0),
        }
      })
      return NextResponse.json({
        healthScore: clampScore(Number(latestModel.score ?? 0)),
        dimensions,
        trendData,
      })
    }

    const { data: runs } = await supabase
      .from("runs")
      .select("status, duration_ms, approval_status, completed_at, created_at")
      .eq("org_id", orgId)
      .eq("workflow_id", id)
      .order("created_at", { ascending: false })
      .limit(100)

    const totalRuns = runs?.length ?? 0
    const completed = (runs ?? []).filter((run) => run.status === "completed")
    const failed = (runs ?? []).filter((run) => run.status === "failed").length
    const approvalPending = (runs ?? []).filter((run) => run.approval_status === "pending").length
    const avgDuration = completed.length
      ? completed.reduce((acc, run) => acc + Number(run.duration_ms ?? 0), 0) / completed.length
      : 0

    const reliability = totalRuns > 0 ? ((completed.length - failed) / totalRuns) * 100 : 0
    const speed = totalRuns > 0 ? Math.max(0, 100 - avgDuration / 1000) : 0
    const overrideRate = totalRuns > 0 ? (approvalPending / totalRuns) * 100 : 0
    const goalCompletion = totalRuns > 0 ? (completed.length / totalRuns) * 100 : 0
    const decisionAccuracy = reliability
    const costEfficiency = totalRuns > 0 ? Math.max(0, 100 - failed * 5) : 0
    const healthScore = clampScore(
      (reliability + speed + costEfficiency + (100 - overrideRate) + goalCompletion + decisionAccuracy) / 6
    )

    const trendData = (runs ?? []).slice(0, 7).reverse().map((run) => ({
      recordedAt: run.created_at,
      healthScore: clampScore(run.status === "completed" ? 85 : run.status === "failed" ? 35 : 60),
    }))

    return NextResponse.json({
      healthScore,
      dimensions: {
        reliability: clampScore(reliability),
        speed: clampScore(speed),
        costEfficiency: clampScore(costEfficiency),
        overrideRate: clampScore(overrideRate),
        goalCompletion: clampScore(goalCompletion),
        decisionAccuracy: clampScore(decisionAccuracy),
      },
      trendData,
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
