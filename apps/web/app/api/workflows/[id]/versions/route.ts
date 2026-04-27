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

    const { data: workflow, error: workflowError } = await supabase
      .from("workflows")
      .select("id, name, updated_at, config")
      .eq("org_id", orgId)
      .eq("id", id)
      .single()
    if (workflowError) {
      return NextResponse.json({ error: workflowError.message }, { status: workflowError.code === "PGRST116" ? 404 : 500 })
    }

    const { data: snapshots } = await supabase
      .from("workflow_health_snapshots")
      .select("score, recorded_at")
      .eq("org_id", orgId)
      .eq("workflow_id", id)
      .order("recorded_at", { ascending: false })
      .limit(20)

    const config =
      workflow.config && typeof workflow.config === "object"
        ? (workflow.config as Record<string, unknown>)
        : {}
    const currentVersion = Number(config.version ?? 1)
    const versionHistory = Array.isArray(config.versionHistory)
      ? (config.versionHistory as Array<Record<string, unknown>>)
      : []

    const snapshotScores = (snapshots ?? []).map((row) => ({
      score: row.score,
      recordedAt: row.recorded_at,
    }))

    const history =
      versionHistory.length > 0
        ? versionHistory.map((entry) => ({
            version: Number(entry.version ?? 1),
            changeSummary: String(entry.summary ?? "Workflow configuration update"),
            appliedAt: entry.appliedAt ?? workflow.updated_at,
            healthScore: snapshotScores[0]?.score ?? null,
          }))
        : [
            {
              version: currentVersion,
              changeSummary: "Current workflow version",
              appliedAt: workflow.updated_at,
              healthScore: snapshotScores[0]?.score ?? null,
            },
          ]

    return NextResponse.json({
      workflow: snakeToCamel<Record<string, unknown>>(workflow),
      versions: history,
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
