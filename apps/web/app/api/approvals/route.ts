import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, getRouteClientAuthMode, resolveOrgId } from "@/lib/supabase/server"
import { ensureDemoDataForOrg } from "@/lib/supabase/demo-bootstrap"
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

    const diagnostics = await getOrgCountDiagnostics(supabase, "approvals", orgId)
    const { data, error } = await supabase
      .from("approvals")
      .select("*")
      .eq("org_id", orgId)
      .order("requested_at", { ascending: false })

    if (error) {
      return NextResponse.json(
        {
          error: error.message,
          ...(debugEnabled
            ? {
                _debug: {
                  resolvedOrgId: orgId,
                  table: "approvals",
                  ...diagnostics,
                  authMode,
                },
              }
            : {}),
        },
        { status: 500 }
      )
    }

    if ((data ?? []).length === 0) {
      console.warn("Approvals route returned empty result", {
        orgId,
        diagnostics,
        authMode,
      })
    }

    return NextResponse.json({
      approvals: (data ?? []).map((row) => snakeToCamel<Record<string, unknown>>(row)),
      ...(debugEnabled
        ? {
            _debug: {
              resolvedOrgId: orgId,
              table: "approvals",
              ...diagnostics,
              queryError: null,
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
