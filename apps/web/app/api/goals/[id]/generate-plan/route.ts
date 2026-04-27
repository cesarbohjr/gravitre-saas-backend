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
    const objective = String(body.objective ?? "").trim()
    const context = String(body.context ?? "")
    const constraints = Array.isArray(body.constraints) ? body.constraints : []

    const { data: goalRow, error: goalError } = await supabase
      .from("goals")
      .select("*")
      .eq("org_id", orgId)
      .eq("id", id)
      .single()

    if (goalError) {
      return NextResponse.json({ error: goalError.message }, { status: goalError.code === "PGRST116" ? 404 : 500 })
    }

    // TODO: Replace placeholder plan generation with real AI planner integration.
    const effectiveObjective = objective || String(goalRow.objective ?? "Define measurable goal outcome")
    const proposedSteps = [
      { id: "step-1", title: "Baseline current performance", owner: "operations", status: "planned" },
      { id: "step-2", title: `Execute: ${effectiveObjective}`, owner: "primary-agent", status: "planned" },
      { id: "step-3", title: "Review outcomes and iterate", owner: "council", status: "planned" },
    ]
    const requiredConnectors = Array.isArray(goalRow.connected_systems)
      ? goalRow.connected_systems
      : ["slack", "postgres"]
    const requiredAgents = [] as string[]
    const approvalGates = [
      { phase: "pre-launch", required: true, approverRole: "owner" },
      { phase: "post-launch", required: true, approverRole: "operator" },
    ]
    const estimatedImpact = {
      confidence: 0.62,
      expectedLift: "8-15%",
      contextSummary: context || "No additional context provided.",
      constraints,
    }

    const { data: plan, error: insertError } = await supabase
      .from("goal_plans")
      .insert({
        org_id: orgId,
        goal_id: id,
        proposed_steps: proposedSteps,
        required_connectors: requiredConnectors,
        required_agents: requiredAgents,
        approval_gates: approvalGates,
        estimated_impact: estimatedImpact,
      })
      .select("*")
      .single()

    if (insertError) {
      return NextResponse.json({ error: insertError.message }, { status: 500 })
    }

    const model = snakeToCamel<Record<string, unknown>>(plan)
    return NextResponse.json({
      goalPlan: model,
      proposedSteps: model.proposedSteps ?? [],
      requiredConnectors: model.requiredConnectors ?? [],
      requiredAgents: model.requiredAgents ?? [],
      approvalGates: model.approvalGates ?? [],
      estimatedImpact: model.estimatedImpact ?? {},
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
