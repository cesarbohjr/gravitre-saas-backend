import { NextRequest, NextResponse } from "next/server"
import { snakeToCamel } from "@/lib/supabase/transforms"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"

function clampConfidence(value: number) {
  if (Number.isNaN(value)) return 0.5
  return Math.max(0, Math.min(1, value))
}

export async function POST(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    const body = (await request.json()) as Record<string, unknown>
    const participatingAgents = Array.isArray(body.participatingAgents) ? body.participatingAgents : []
    const objective = String(body.objective ?? "").trim()
    const context = String(body.context ?? "")
    const evidenceSources = Array.isArray(body.evidenceSources) ? body.evidenceSources : []
    const debateModeRaw = String(body.debateMode ?? "consensus")
    const debateMode =
      debateModeRaw === "majority_vote" || debateModeRaw === "lead_decides" ? debateModeRaw : "consensus"

    if (!objective) {
      return NextResponse.json({ error: "objective is required" }, { status: 400 })
    }

    const { data: session, error: sessionError } = await supabase
      .from("council_sessions")
      .insert({
        org_id: orgId,
        objective,
        participating_agents: participatingAgents,
        debate_mode: debateMode,
        status: "in_progress",
      })
      .select("*")
      .single()

    if (sessionError) {
      return NextResponse.json({ error: sessionError.message }, { status: 500 })
    }

    // TODO: Replace placeholder contribution generation with real multi-agent reasoning.
    const generatedContributions = (participatingAgents as Array<Record<string, unknown>>).map((agent, index) => {
      const agentId = typeof agent.id === "string" ? agent.id : null
      const agentName = typeof agent.name === "string" ? agent.name : `Agent ${index + 1}`
      const confidence = clampConfidence(0.55 + index * 0.08)
      return {
        org_id: orgId,
        session_id: session.id,
        agent_id: agentId,
        position: `${agentName} proposes a constrained path to objective completion.`,
        confidence,
        reasoning: `Context considered: ${context || "limited context"}. Evidence reviewed: ${
          evidenceSources.length > 0 ? evidenceSources.join(", ") : "none provided"
        }.`,
        evidence_used: evidenceSources,
      }
    })

    const { data: contributionRows, error: contributionError } = generatedContributions.length
      ? await supabase.from("council_contributions").insert(generatedContributions).select("*")
      : await supabase.from("council_contributions").select("*").eq("session_id", session.id).limit(0)

    if (contributionError) {
      return NextResponse.json({ error: contributionError.message }, { status: 500 })
    }

    const contributions = (contributionRows ?? []).map((row) => snakeToCamel<Record<string, unknown>>(row))
    return NextResponse.json(
      {
        councilId: session.id,
        status: session.status,
        agentPositions: contributions.map((item) => item.position ?? ""),
        confidenceScores: contributions.map((item) => item.confidence ?? 0),
        reasoning: contributions.map((item) => item.reasoning ?? ""),
        contributions,
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
