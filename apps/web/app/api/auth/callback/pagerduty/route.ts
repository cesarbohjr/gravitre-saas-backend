import { NextRequest, NextResponse } from "next/server"

/**
 * PagerDuty OAuth redirect (locked in PD app as gravitre.app/api/auth/callback/pagerduty).
 * Forwards code/state to the FastAPI connector callback, which completes OAuth and
 * redirects the browser to /connectors.
 */
function backendBase(): string {
  const base =
    process.env.FASTAPI_BASE_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    "https://gravitre-saas-backend-production.up.railway.app"
  return base.replace(/\/+$/, "")
}

export async function GET(request: NextRequest) {
  const incoming = new URL(request.url)
  const target = new URL(`${backendBase()}/api/connectors/oauth/pagerduty/callback`)
  incoming.searchParams.forEach((value, key) => {
    target.searchParams.set(key, value)
  })
  return NextResponse.redirect(target.toString(), 302)
}
