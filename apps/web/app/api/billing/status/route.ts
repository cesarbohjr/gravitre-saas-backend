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

function isMissingOrganizationsTableError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? "")
  const lower = message.toLowerCase()
  return lower.includes("public.organizations") && (lower.includes("does not exist") || lower.includes("schema cache"))
}

export async function GET(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }

    let { data: orgData, error } = await supabase
      .from("organizations")
      .select("settings")
      .eq("id", orgId)
      .maybeSingle()

    // Only bootstrap demo rows when the org is missing.
    // This avoids clobbering existing organization settings (including billing state).
    if (!error && !orgData) {
      await ensureDemoDataForOrg(supabase, orgId)
      const retry = await supabase
        .from("organizations")
        .select("settings")
        .eq("id", orgId)
        .maybeSingle()
      orgData = retry.data
      error = retry.error
    }

    if (error) {
      if (isMissingOrganizationsTableError(error)) {
        return NextResponse.json({
          billingStatus: "inactive",
          currentPeriodEnd: null,
          cancelAtPeriodEnd: false,
        })
      }
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
