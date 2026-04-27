import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"

interface RouteParams {
  params: Promise<{ id: string }>
}

function toPercent(numerator: number, denominator: number) {
  if (denominator <= 0) return 0
  return Math.max(0, Math.min(100, (numerator / denominator) * 100))
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  try {
    const { id } = await params
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const { data: system, error: systemError } = await supabase
      .from("connected_systems")
      .select("*")
      .eq("org_id", orgId)
      .eq("id", id)
      .single()
    if (systemError) {
      return NextResponse.json({ error: systemError.message }, { status: systemError.code === "PGRST116" ? 404 : 500 })
    }

    const { data: runs } = await supabase
      .from("runs")
      .select("status, created_at, completed_at")
      .eq("org_id", orgId)
      .order("created_at", { ascending: false })
      .limit(120)

    const { data: logs } = await supabase
      .from("audit_logs")
      .select("severity, created_at")
      .eq("org_id", orgId)
      .order("created_at", { ascending: false })
      .limit(120)

    const totalRuns = runs?.length ?? 0
    const successRuns = (runs ?? []).filter((run) => run.status === "completed").length
    const failedRuns = (runs ?? []).filter((run) => run.status === "failed").length
    const recentErrors = (logs ?? []).filter((log) => log.severity === "error").length

    const config =
      system.config && typeof system.config === "object" ? (system.config as Record<string, unknown>) : {}
    const avgLatency = Number(config.avgLatencyMs ?? 0)
    const rateLimitHits = Number(config.rateLimitHits ?? 0)

    return NextResponse.json({
      successRate: toPercent(successRuns, totalRuns),
      avgLatency: avgLatency || 0,
      errorCount: Math.max(failedRuns, recentErrors),
      rateLimitHits,
      lastSuccessfulSync: system.last_synced_at ?? null,
      status: system.status,
      trendOverTime: (runs ?? [])
        .slice(0, 7)
        .reverse()
        .map((run) => ({
          timestamp: run.created_at,
          success: run.status === "completed",
        })),
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
