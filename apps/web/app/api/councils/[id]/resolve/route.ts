import { NextRequest, NextResponse } from "next/server"
import { snakeToCamel } from "@/lib/supabase/transforms"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"

interface RouteParams {
  params: Promise<{ id: string }>
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  try {
    const { id } = await params
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const body = (await request.json()) as Record<string, unknown>
    const finalDecision = (body.finalDecision as Record<string, unknown> | undefined) ?? {}
    const dissentingOpinions = Array.isArray(body.dissentingOpinions) ? body.dissentingOpinions : []
    const humanOverride = Boolean(body.humanOverride ?? false)

    const { data, error } = await supabase
      .from("council_sessions")
      .update({
        final_decision: {
          ...finalDecision,
          humanOverride,
          resolvedAt: new Date().toISOString(),
        },
        dissenting_opinions: dissentingOpinions,
        status: "resolved",
      })
      .eq("org_id", orgId)
      .eq("id", id)
      .select("*")
      .single()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: error.code === "PGRST116" ? 404 : 500 })
    }

    return NextResponse.json({ council: snakeToCamel<Record<string, unknown>>(data) })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
