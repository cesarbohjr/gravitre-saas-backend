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

    const { data: session, error: sessionError } = await supabase
      .from("council_sessions")
      .select("*")
      .eq("org_id", orgId)
      .eq("id", id)
      .single()
    if (sessionError) {
      return NextResponse.json(
        { error: sessionError.message },
        { status: sessionError.code === "PGRST116" ? 404 : 500 }
      )
    }

    const { data: contributionRows, error: contributionError } = await supabase
      .from("council_contributions")
      .select("*")
      .eq("org_id", orgId)
      .eq("session_id", id)
      .order("created_at", { ascending: true })

    if (contributionError) {
      return NextResponse.json({ error: contributionError.message }, { status: 500 })
    }

    const contributions = (contributionRows ?? []).map((row) => snakeToCamel<Record<string, unknown>>(row))
    const uniquePositions = new Set(
      contributions.map((row) => String(row.position ?? "").toLowerCase().trim()).filter(Boolean)
    )

    return NextResponse.json({
      council: snakeToCamel<Record<string, unknown>>(session),
      timelineProgress: {
        startedAt: session.created_at,
        updatedAt: session.updated_at,
        contributionCount: contributions.length,
      },
      agentContributions: contributions,
      disagreementsDetected: uniquePositions.size > 1,
      status: session.status,
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
