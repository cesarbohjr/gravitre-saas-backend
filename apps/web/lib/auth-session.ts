import type { NextRequest, NextResponse } from "next/server"

/** Canonical browser origin for auth redirects (avoids www/non-www cookie splits). */
export function getAppOrigin(request?: NextRequest): string {
  const configured = (process.env.NEXT_PUBLIC_APP_URL || "").trim().replace(/\/+$/, "")
  if (configured) return configured

  if (request) {
    const forwardedHost = request.headers.get("x-forwarded-host")
    const forwardedProto = request.headers.get("x-forwarded-proto") || "https"
    if (forwardedHost) {
      return `${forwardedProto}://${forwardedHost}`
    }
    return new URL(request.url).origin
  }

  if (typeof window !== "undefined") {
    return window.location.origin
  }

  return ""
}

export function isSupabaseAuthCookie(name: string): boolean {
  return name.startsWith("sb-") || name.includes("supabase-auth-token")
}

/** Remove broken Supabase auth cookies so OAuth can start clean. */
export function clearSupabaseAuthCookiesOnResponse(response: NextResponse): void {
  const candidates = [
    "sb-access-token",
    "sb-refresh-token",
    "supabase-auth-token",
    "supabase-auth-token-code-verifier",
  ]
  for (const name of candidates) {
    response.cookies.delete(name)
  }
}

export function clearSupabaseAuthCookiesFromRequest(
  request: NextRequest,
  response: NextResponse
): void {
  for (const cookie of request.cookies.getAll()) {
    if (isSupabaseAuthCookie(cookie.name)) {
      response.cookies.delete(cookie.name)
    }
  }
}
