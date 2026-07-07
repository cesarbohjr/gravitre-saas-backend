import { NextRequest, NextResponse } from "next/server"

import { backendBaseUrl, publicAppUrl } from "@/lib/public-urls"

/**
 * Complete connector OAuth on FastAPI and forward the browser to the app
 * success/error URL. App Router routes take precedence over /api rewrites so
 * OAuth providers always receive a reliable redirect back to Gravitre.
 */
export async function completeConnectorOAuthCallback(
  request: NextRequest,
  provider: string,
): Promise<NextResponse> {
  const backendUrl = backendBaseUrl()
  const target = new URL(`${backendUrl}/api/connectors/oauth/${provider}/callback`)
  request.nextUrl.searchParams.forEach((value, key) => {
    target.searchParams.set(key, value)
  })

  try {
    const response = await fetch(target.toString(), {
      method: "GET",
      redirect: "manual",
      cache: "no-store",
    })

    if (response.status >= 300 && response.status < 400) {
      const location = response.headers.get("location")
      if (location) {
        return NextResponse.redirect(location, 302)
      }
    }

    const body = await response.text().catch(() => "")
    console.error(
      "[oauth] connector callback did not redirect",
      provider,
      response.status,
      body.slice(0, 240),
    )
  } catch (error) {
    console.error("[oauth] connector callback proxy failed", provider, error)
  }

  const fail = new URL("/connectors", publicAppUrl())
  fail.searchParams.set("oauth", "error")
  fail.searchParams.set("provider", provider)
  fail.searchParams.set("message", "callback_redirect_failed")
  return NextResponse.redirect(fail.toString(), 302)
}
