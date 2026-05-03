import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { ensureDemoDataForOrg } from "@/lib/supabase/demo-bootstrap"

function normalizeStatus(input: unknown): "active" | "inactive" | "cancelled_pending" | "cancelled" {
  const value = String(input ?? "").toLowerCase()
  if (value === "active" || value === "cancelled_pending" || value === "cancelled") {
    return value
  }
  return "inactive"
}

export async function GET(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    await ensureDemoDataForOrg(supabase, orgId)

    const { data: orgData, error } = await supabase
      .from("organizations")
      .select("settings")
      .eq("id", orgId)
      .maybeSingle()

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    const settings = (orgData?.settings as Record<string, unknown> | null) ?? {}
    const billing = (settings.billing as Record<string, unknown> | undefined) ?? {}
    const billingStatus = normalizeStatus(billing.subscriptionStatus)
    const currentPeriodEnd = billing.renewsAt ? String(billing.renewsAt) : null
    const cancelAtPeriodEnd = billingStatus === "cancelled_pending"

    return NextResponse.json({
      billingStatus,
      currentPeriodEnd,
      cancelAtPeriodEnd,
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
