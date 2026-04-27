import { NextRequest, NextResponse } from "next/server"
import { snakeToCamel } from "@/lib/supabase/transforms"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"

interface RouteParams {
  params: Promise<{ id: string; rec_id: string }>
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  try {
    const { id, rec_id: recId } = await params
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const { data: recommendation, error: recommendationError } = await supabase
      .from("optimization_recommendations")
      .update({
        status: "applied",
      })
      .eq("org_id", orgId)
      .eq("workflow_id", id)
      .eq("id", recId)
      .select("*")
      .single()

    if (recommendationError) {
      return NextResponse.json(
        { error: recommendationError.message },
        { status: recommendationError.code === "PGRST116" ? 404 : 500 }
      )
    }

    const { data: workflow, error: workflowError } = await supabase
      .from("workflows")
      .select("id, config")
      .eq("org_id", orgId)
      .eq("id", id)
      .single()
    if (workflowError) {
      return NextResponse.json(
        { error: workflowError.message },
        { status: workflowError.code === "PGRST116" ? 404 : 500 }
      )
    }

    const currentConfig =
      workflow?.config && typeof workflow.config === "object"
        ? (workflow.config as Record<string, unknown>)
        : {}
    const currentVersion = Number(currentConfig.version ?? 1)
    const existingHistory = Array.isArray(currentConfig.versionHistory)
      ? (currentConfig.versionHistory as Array<Record<string, unknown>>)
      : []
    const recommendationModel = snakeToCamel<Record<string, unknown>>(recommendation)
    const nextVersion = currentVersion + 1

    const versionHistory = [
      ...existingHistory,
      {
        version: nextVersion,
        appliedRecommendationId: recommendationModel.id,
        issue: recommendationModel.issue ?? null,
        summary: "Applied optimization recommendation",
        appliedAt: new Date().toISOString(),
      },
    ]

    const nextConfig = {
      ...currentConfig,
      version: nextVersion,
      versionHistory,
    }

    const { error: updateError } = await supabase
      .from("workflows")
      .update({ config: nextConfig })
      .eq("org_id", orgId)
      .eq("id", id)
    if (updateError) {
      return NextResponse.json({ error: updateError.message }, { status: 500 })
    }

    return NextResponse.json({
      recommendation: recommendationModel,
      workflowVersion: nextVersion,
      applied: true,
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
