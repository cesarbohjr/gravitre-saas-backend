import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { snakeToCamel } from "@/lib/supabase/transforms"

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

    const [{ data: runData, error: runError }, { data: stepData, error: stepError }] = await Promise.all([
      supabase.from("runs").select("*").eq("org_id", orgId).eq("id", id).single(),
      supabase
        .from("run_steps")
        .select("*")
        .eq("org_id", orgId)
        .eq("run_id", id)
        .order("order_index", { ascending: true }),
    ])

    if (runError) {
      return NextResponse.json({ error: runError.message }, { status: runError.code === "PGRST116" ? 404 : 500 })
    }
    if (stepError) {
      return NextResponse.json({ error: stepError.message }, { status: 500 })
    }

    let workflowName: string | null = runData.workflow_name ?? null
    if (!workflowName && runData.workflow_id) {
      const { data: workflowData } = await supabase
        .from("workflows")
        .select("name")
        .eq("org_id", orgId)
        .eq("id", runData.workflow_id)
        .maybeSingle()
      workflowName = workflowData?.name ?? null
    }

    return NextResponse.json({
      run: {
        ...snakeToCamel<Record<string, unknown>>(runData),
        workflowName: workflowName ?? "Workflow",
      },
      steps: (stepData ?? []).map((step) => snakeToCamel<Record<string, unknown>>(step)),
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
