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

    const { data, error } = await supabase
      .from("approvals")
      .select("*")
      .eq("org_id", orgId)
      .order("requested_at", { ascending: false })

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({
      approvals: (data ?? []).map((row) => snakeToCamel<Record<string, unknown>>(row)),
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
