import { NextRequest, NextResponse } from "next/server"

import { backendBaseUrl } from "@/lib/public-urls"

/** Decode unsigned OAuth state payload to route domain-only vendor callbacks. */
export function oauthStateProvider(state: string | null): string | null {
  if (!state || !state.includes(".")) return null
  const body = state.split(".")[0]
  if (!body) return null
  try {
    const padded = body.padEnd(body.length + ((4 - (body.length % 4)) % 4), "=")
    const decoded = atob(padded.replace(/-/g, "+").replace(/_/g, "/"))
    const json = JSON.parse(decoded) as { provider?: string }
    return typeof json.provider === "string" ? json.provider : null
  } catch {
    return null
  }
}

/** ClickUp stores gravitre.app only — forward root ?code=&state= to the API callback. */
export function clickupRootOAuthRedirect(request: NextRequest): NextResponse | null {
  if (request.nextUrl.pathname !== "/") return null
  const code = request.nextUrl.searchParams.get("code")
  const state = request.nextUrl.searchParams.get("state")
  if (!code || !state) return null
  if (oauthStateProvider(state) !== "clickup") return null

  const target = new URL(`${backendBaseUrl()}/api/connectors/oauth/clickup/callback`)
  request.nextUrl.searchParams.forEach((value, key) => {
    target.searchParams.set(key, value)
  })
  return NextResponse.redirect(target.toString(), 302)
}

export function forwardClickupOAuthCallback(request: NextRequest): NextResponse {
  const incoming = new URL(request.url)
  const target = new URL(`${backendBaseUrl()}/api/connectors/oauth/clickup/callback`)
  incoming.searchParams.forEach((value, key) => {
    target.searchParams.set(key, value)
  })
  return NextResponse.redirect(target.toString(), 302)
}
