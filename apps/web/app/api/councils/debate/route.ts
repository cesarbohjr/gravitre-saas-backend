import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
import { createSupabaseServerClient } from "@/lib/supabase-server"

function mapDecisionMethod(mode: string): string {
  if (mode === "majority_vote") return "majority_vote"
  if (mode === "lead_decides") return "chair_decides"
  return "majority_vote"
}

export async function POST(request: NextRequest) {
  const body = (await request.json()) as Record<string, unknown>
  const participatingAgents = Array.isArray(body.participatingAgents) ? body.participatingAgents : []
  const objective = String(body.objective ?? "").trim()
  const context = String(body.context ?? "")
  const evidenceSources = Array.isArray(body.evidenceSources) ? body.evidenceSources : []
  const debateModeRaw = String(body.debateMode ?? "consensus")

  if (!objective) {
    return NextResponse.json({ error: "objective is required" }, { status: 400 })
  }

  const agents = (participatingAgents as Array<Record<string, unknown>>).map((agent, index) => ({
    name: typeof agent.name === "string" ? agent.name : `Agent ${index + 1}`,
    role: typeof agent.role === "string" ? agent.role : "analyst",
    weight: typeof agent.weight === "number" ? agent.weight : 1,
  }))

  const backendBody = JSON.stringify({
    objective,
    options: ["proceed", "defer", "reject"],
    agents,
    evidence: { context, evidenceSources },
    decision_method: mapDecisionMethod(debateModeRaw),
    max_rounds: 1,
  })

  const proxyRequest = new NextRequest(request.url, {
    method: "POST",
    headers: request.headers,
    body: backendBody,
  })
  proxyRequest.headers.set("content-type", "application/json")

  const upstream = await proxyToFastApi(proxyRequest, "/api/agent-council/start")
  if (!upstream.ok) {
    return upstream
  }

  const session = (await upstream.json()) as Record<string, unknown>
  const lastRound = Array.isArray(session.debate_rounds)
    ? (session.debate_rounds[session.debate_rounds.length - 1] as Record<string, unknown>)
    : null
  const opinions = Array.isArray(lastRound?.opinions) ? (lastRound?.opinions as Array<Record<string, unknown>>) : []

  const contributions = opinions.map((opinion) => ({
    position: opinion.position ?? "",
    confidence: opinion.confidence ?? 0,
    reasoning: opinion.reasoning ?? "",
    agentName: opinion.agent_name ?? "",
  }))

  let councilId = String(session.id ?? "")
  try {
    const supabase = await createSupabaseServerClient()
    const { data: userData } = await supabase.auth.getUser()
    const orgQuery = await supabase.from("organization_members").select("org_id").limit(1).maybeSingle()
    const orgId = orgQuery.data?.org_id
    if (orgId) {
      const { data: inserted } = await supabase
        .from("council_sessions")
        .insert({
          org_id: orgId,
          objective,
          participating_agents: participatingAgents,
          debate_mode: debateModeRaw,
          status: "completed",
        })
        .select("id")
        .single()
      if (inserted?.id) councilId = String(inserted.id)
    }
  } catch {
    // Best-effort session persistence; governed AI result is still returned.
  }

  return NextResponse.json(
    {
      councilId,
      status: session.status ?? "completed",
      agentPositions: contributions.map((item) => item.position),
      confidenceScores: contributions.map((item) => item.confidence),
      reasoning: contributions.map((item) => item.reasoning),
      contributions,
      finalRecommendation: session.final_recommendation,
      finalConfidence: session.final_confidence,
    },
    { status: 201 },
  )
}
