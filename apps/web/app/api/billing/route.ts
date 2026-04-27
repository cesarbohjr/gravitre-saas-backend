import { NextRequest, NextResponse } from "next/server"
import { createSupabaseRouteClient, resolveOrgId } from "@/lib/supabase/server"
import { ensureDemoDataForOrg } from "@/lib/supabase/demo-bootstrap"
import { snakeToCamel } from "@/lib/supabase/transforms"

type BillingAction =
  | "upgrade_plan"
  | "cancel_subscription"
  | "update_card"
  | "update_address"
  | "download_invoice"
  | "export_invoices"

function toIsoDate(value: unknown, fallback: string) {
  const stringValue = String(value ?? "").trim()
  if (!stringValue) return fallback
  const date = new Date(stringValue)
  return Number.isNaN(date.getTime()) ? fallback : date.toISOString()
}

export async function GET(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }
    await ensureDemoDataForOrg(supabase, orgId)

    const { data: orgData, error: orgError } = await supabase
      .from("organizations")
      .select("id, name, settings")
      .eq("id", orgId)
      .maybeSingle()

    if (orgError) {
      return NextResponse.json({ error: orgError.message }, { status: 500 })
    }

    const settings = (orgData?.settings as Record<string, unknown> | null) ?? {}
    const billing = (settings.billing as Record<string, unknown> | undefined) ?? {}
    const invoices = Array.isArray(billing.invoices)
      ? billing.invoices.map((invoice) => (typeof invoice === "object" && invoice ? invoice : {}))
      : []

    const { data: eventsData, error: eventsError } = await supabase
      .from("billing_events")
      .select("id, org_id, action, status, payload, created_at")
      .eq("org_id", orgId)
      .order("created_at", { ascending: false })
      .limit(100)

    const billingEvents =
      eventsError && eventsError.message.toLowerCase().includes("does not exist")
        ? []
        : (eventsData ?? []).map((event) => snakeToCamel<Record<string, unknown>>(event))

    return NextResponse.json({
      billing: {
        plan: String(billing.plan ?? "business"),
        subscriptionStatus: String(billing.subscriptionStatus ?? "active"),
        renewsAt: toIsoDate(billing.renewsAt, new Date(Date.now() + 1000 * 60 * 60 * 24 * 30).toISOString()),
        cardLast4: String(billing.cardLast4 ?? "4242"),
        billingAddress:
          (billing.billingAddress as Record<string, unknown> | undefined) ?? {
            street: "123 Market Street",
            city: "San Francisco",
            state: "CA",
            zip: "94102",
            country: "United States",
          },
        invoices,
        events: billingEvents,
      },
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const supabase = createSupabaseRouteClient(request)
    const orgId = await resolveOrgId(supabase, request)
    if (!orgId) {
      return NextResponse.json({ error: "Organization context required" }, { status: 403 })
    }
    await ensureDemoDataForOrg(supabase, orgId)

    const body = (await request.json().catch(() => ({}))) as Record<string, unknown>
    const action = String(body.action ?? "").toLowerCase() as BillingAction
    if (!action) {
      return NextResponse.json({ error: "action is required" }, { status: 400 })
    }

    const { data: orgData, error: orgError } = await supabase
      .from("organizations")
      .select("settings")
      .eq("id", orgId)
      .maybeSingle()

    if (orgError) {
      return NextResponse.json({ error: orgError.message }, { status: 500 })
    }

    const currentSettings = (orgData?.settings as Record<string, unknown> | null) ?? {}
    const currentBilling = (currentSettings.billing as Record<string, unknown> | undefined) ?? {}
    const updatedBilling: Record<string, unknown> = { ...currentBilling }

    if (action === "upgrade_plan") {
      updatedBilling.plan = String(body.planId ?? body.plan ?? "business")
      updatedBilling.subscriptionStatus = "active"
    }
    if (action === "cancel_subscription") {
      updatedBilling.subscriptionStatus = "cancelled_pending"
    }
    if (action === "update_card") {
      const cardNumber = String(body.cardNumber ?? "").replace(/\D/g, "")
      updatedBilling.cardLast4 = cardNumber.slice(-4) || String(currentBilling.cardLast4 ?? "4242")
    }
    if (action === "update_address") {
      updatedBilling.billingAddress = {
        street: String(body.street ?? ""),
        city: String(body.city ?? ""),
        state: String(body.state ?? ""),
        zip: String(body.zip ?? ""),
        country: String(body.country ?? ""),
      }
    }

    const nextSettings = {
      ...currentSettings,
      billing: updatedBilling,
    }

    const { error: updateError } = await supabase
      .from("organizations")
      .update({ settings: nextSettings })
      .eq("id", orgId)

    if (updateError) {
      return NextResponse.json({ error: updateError.message }, { status: 500 })
    }

    let event: Record<string, unknown> | null = null
    const { data: eventData, error: eventError } = await supabase
      .from("billing_events")
      .insert({
        org_id: orgId,
        action,
        status: "success",
        payload: body,
      })
      .select("id, org_id, action, status, payload, created_at")
      .single()

    if (!eventError && eventData) {
      event = snakeToCamel<Record<string, unknown>>(eventData)
    }

    return NextResponse.json({
      success: true,
      action,
      event,
      billing: snakeToCamel<Record<string, unknown>>({ ...updatedBilling }),
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
