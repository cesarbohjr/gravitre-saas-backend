import { NextResponse, type NextRequest } from "next/server"

import { clickupRootOAuthRedirect } from "@/lib/clickup-oauth-callback"
import { redirectToLogin, updateSession } from "@/lib/supabase/middleware"

export async function proxy(request: NextRequest) {
  const pathname = request.nextUrl.pathname

  const clickupRedirect = clickupRootOAuthRedirect(request)
  if (clickupRedirect) {
    return clickupRedirect
  }

  const { response: supabaseResponse, user } = await updateSession(request)

  const playwrightE2ePaths = ["/e2e"]

  const publicPaths = [
    "/",
    "/login",
    "/get-started",
    "/auth",
    // Public marketing pages — must stay in sync with app/(marketing) so they
    // remain reachable by anonymous visitors and search crawlers.
    "/pricing",
    "/features",
    "/about",
    "/docs",
    "/blog",
    "/contact",
    "/careers",
    "/changelog",
    "/guides",
    "/roadmap",
    "/support",
    "/api",
    "/forgot-password",
    "/privacy",
    "/terms",
    "/security",
    "/api/auth",
    "/_next",
    "/favicon",
    "/robots.txt",
    "/sitemap",
    ...playwrightE2ePaths,
  ]

  const isPublicPath = publicPaths.some(
    (p) =>
      pathname === p ||
      pathname.startsWith(`${p}/`) ||
      (p !== "/" && pathname.startsWith(p))
  )

  const isApiRoute = pathname.startsWith("/api/")

  if (isPublicPath || isApiRoute) {
    return supabaseResponse
  }

  if (!user) {
    const hadSupabaseSession = request.cookies
      .getAll()
      .some((c) => c.name.startsWith("sb-") || c.name.includes("supabase-auth-token"))
    return redirectToLogin(request, { staleSession: hadSupabaseSession })
  }

  return supabaseResponse
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|css|js)$).*)",
  ],
}
