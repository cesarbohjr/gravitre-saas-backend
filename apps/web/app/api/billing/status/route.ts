import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
import { createSupabaseServerClient } from "@/lib/supabase-server"

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" } as const

/** Do not grant access when backend billing is unavailable — client uses session 402 state. */
function degradedBillingStatus(reason: string) {
  return {
    billingStatus: "unknown",
    planCode: "node",
    canAccessApp: null,
    requiresUpgrade: false,
    upgradeReason: null,
    trialEndsAt: null,
    currentPeriodEnd: null,
    cancelAtPeriodEnd: false,
    trialExpired: false,
    billingState: "unknown",
    billingKnown: false,
    _auth_degraded: true,
    _degraded_reason: reason,
  }
}

export async function GET(request: NextRequest) {
  const supabase = await createSupabaseServerClient()
  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser()

  if (userError || !user) {
    return NextResponse.json(
      { error: "Unauthorized", detail: userError?.message ?? "No session" },
      { status: 401, headers: JSON_HEADERS },
    )
  }

  const {
    data: { session },
  } = await supabase.auth.getSession()

  const accessToken = session?.access_token
  const authHeader = request.headers.get("authorization")
  const bearer =
    authHeader?.startsWith("Bearer ") ? authHeader : accessToken ? `Bearer ${accessToken}` : null

  if (!bearer) {
    return NextResponse.json(degradedBillingStatus("missing_bearer"), {
      status: 200,
      headers: JSON_HEADERS,
    })
  }

  const headers = new Headers(request.headers)
  headers.set("authorization", bearer)

  const proxied = await proxyToFastApi(
    new NextRequest(request.url, { method: "GET", headers }),
    "/api/billing/status",
  )

  if (proxied.status === 401 || proxied.status === 500 || proxied.status === 502) {
    console.warn(
      "[api/billing/status] Backend unavailable for user=%s status=%s — returning fallback",
      user.email ?? user.id,
      proxied.status,
    )
    return NextResponse.json(degradedBillingStatus(`backend_${proxied.status}`), {
      status: 200,
      headers: JSON_HEADERS,
    })
  }

  return proxied
}
