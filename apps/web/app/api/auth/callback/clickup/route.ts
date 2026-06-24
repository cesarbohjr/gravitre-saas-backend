import { NextRequest, NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/public-urls"

/**
 * ClickUp OAuth redirect — shorter path for ClickUp app settings (their UI rejects long URLs).
 * Forwards code/state to the FastAPI connector callback, which completes OAuth and
 * redirects the browser to /connectors.
 */
export async function GET(request: NextRequest) {
  const incoming = new URL(request.url)
  const target = new URL(`${backendBaseUrl()}/api/connectors/oauth/clickup/callback`)
  incoming.searchParams.forEach((value, key) => {
    target.searchParams.set(key, value)
  })
  return NextResponse.redirect(target.toString(), 302)
}
