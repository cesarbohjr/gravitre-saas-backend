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

    const { data, error } = await supabase
      .from("optimization_recommendations")
      .select("*")
      .eq("org_id", orgId)
      .eq("workflow_id", id)
      .order("created_at", { ascending: false })

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    const recommendations = (data ?? []).map((row) => {
      const model = snakeToCamel<Record<string, unknown>>(row)
      return {
        id: model.id,
        issue: model.issue ?? "",
        evidence: model.evidence ?? null,
        suggestedChange: model.suggestedChange ?? {},
        estimatedImpact: model.estimatedImpact ?? {},
        confidence: model.confidence ?? null,
        riskLevel: model.riskLevel ?? null,
        affectedNodes: model.affectedNodes ?? [],
        status: model.status ?? "open",
        createdAt: model.createdAt ?? null,
      }
    })

    return NextResponse.json({ recommendations })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
