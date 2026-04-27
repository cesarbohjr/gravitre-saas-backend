import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, getRouteClientAuthMode, resolveOrgId } from "@/lib/supabase/server"
import { ensureDemoDataForOrg, getDemoRowsForOrg } from "@/lib/supabase/demo-bootstrap"
import { getOrgCountDiagnostics, isDebugRequest } from "@/lib/supabase/route-diagnostics"
import { snakeToCamel } from "@/lib/supabase/transforms"

export async function GET(request: NextRequest) {
  try {
    const debugEnabled = isDebugRequest(request.nextUrl.searchParams)
    const authMode = getRouteClientAuthMode(request)
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }
    await ensureDemoDataForOrg(supabase, orgId)
    const demoRows = getDemoRowsForOrg(orgId)

    const diagnostics = await getOrgCountDiagnostics(supabase, "runs", orgId)
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
      const fallbackRuns = (demoRows?.runs ?? []).map((row) => {
        const model = snakeToCamel<Record<string, unknown>>(row as Record<string, unknown>)
        return {
          ...model,
          workflowName: row.workflow_name ?? "Workflow",
          trigger: row.trigger ?? null,
        }
      })

      return NextResponse.json(
        {
          ...(fallbackRuns.length > 0 ? { runs: fallbackRuns } : { error: error.message }),
          ...(debugEnabled
            ? {
                _debug: {
                  resolvedOrgId: orgId,
                  table: "runs",
                  statusFilter,
                  ...diagnostics,
                  queryError: error.message,
                  fallbackUsed: fallbackRuns.length > 0,
                  authMode,
                },
              }
            : {}),
        },
        { status: fallbackRuns.length > 0 ? 200 : 500 }
      )
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
    if ((data ?? []).length === 0) {
      console.warn("Runs route returned empty result", {
        orgId,
        statusFilter,
        diagnostics,
        authMode,
      })
    }

    const safeRuns =
      runs.length > 0
        ? runs
        : (demoRows?.runs ?? []).map((row) => {
            const model = snakeToCamel<Record<string, unknown>>(row as Record<string, unknown>)
            return {
              ...model,
              workflowName: row.workflow_name ?? "Workflow",
              trigger: row.trigger ?? null,
            }
          })

    return NextResponse.json({
      runs: safeRuns,
      ...(debugEnabled
        ? {
            _debug: {
              resolvedOrgId: orgId,
              table: "runs",
              statusFilter,
              ...diagnostics,
              queryError: null,
              fallbackUsed: runs.length === 0 && safeRuns.length > 0,
              authMode,
            },
          }
        : {}),
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
