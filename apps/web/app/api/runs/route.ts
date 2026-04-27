import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { ensureDemoDataForOrg } from "@/lib/supabase/demo-bootstrap"
import { snakeToCamel } from "@/lib/supabase/transforms"

export async function GET(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }
    await ensureDemoDataForOrg(supabase, orgId)

    const statusFilter = request.nextUrl.searchParams.get("status")
    const requestedStatuses =
      statusFilter
        ?.split(",")
        .map((value) => value.trim())
        .filter(Boolean) ?? []
    const normalizedStatuses = requestedStatuses
      .filter((value) => value !== "needs_approval")
      .flatMap((value) => (value === "queued" ? ["pending"] : [value]))
    const statusValues = Array.from(new Set(normalizedStatuses))
    const includeNeedsApproval = requestedStatuses.includes("needs_approval")

    let query = supabase
      .from("runs")
      .select("*")
      .eq("org_id", orgId)
      .order("created_at", { ascending: false })

    if (includeNeedsApproval && statusValues.length > 0) {
      query = query.or(`status.in.(${statusValues.join(",")}),approval_status.eq.pending`)
    } else if (statusValues.length > 0) {
      query = query.in("status", statusValues)
    } else if (includeNeedsApproval) {
      query = query.eq("approval_status", "pending")
    }

    const { data, error } = await query

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    const workflowIds = Array.from(new Set((data ?? []).map((row) => row.workflow_id).filter(Boolean)))
    let workflowMap: Record<string, string> = {}
    if (workflowIds.length > 0) {
      const { data: workflows } = await supabase
        .from("workflows")
        .select("id, name")
        .eq("org_id", orgId)
        .in("id", workflowIds)
      workflowMap = Object.fromEntries((workflows ?? []).map((workflow) => [workflow.id, workflow.name]))
    }

    const runs = (data ?? []).map((row) => {
      const model = snakeToCamel<Record<string, unknown>>(row)
      return {
        ...model,
        workflowName:
          row.workflow_name ??
          (row.workflow_id ? workflowMap[String(row.workflow_id)] : null) ??
          "Workflow",
        trigger: row.trigger ?? null,
      }
    })
    return NextResponse.json({ runs })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
