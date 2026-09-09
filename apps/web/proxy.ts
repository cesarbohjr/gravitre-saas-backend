import { NextResponse, type NextRequest } from "next/server"

import { clickupRootOAuthRedirect } from "@/lib/clickup-oauth-callback"
import { isMarketingContentRoute } from "@/lib/is-marketing-route"
import { redirectToLogin, updateSession } from "@/lib/supabase/middleware"

function withRouteKind(response: NextResponse, pathname: string): NextResponse {
  response.headers.set("x-pathname", pathname)
  // The unlisted /deck presentation is a standalone surface: route it through
  // the lighter marketing provider tree so the operator AI helper / app shell
  // is not mounted over the slides. Kept out of isMarketingContentRoute so it
  // stays absent from the sitemap and remains noindex.
  const isDeck = pathname === "/deck" || pathname.startsWith("/deck/")
  if (isMarketingContentRoute(pathname) || isDeck) {
    response.headers.set("x-gravitre-marketing", "1")
  }
  return response
}

export async function proxy(request: NextRequest) {
  const pathname = request.nextUrl.pathname

  const clickupRedirect = clickupRootOAuthRedirect(request)
  if (clickupRedirect) {
    return clickupRedirect
  }

  const { response: supabaseResponse, user } = await updateSession(request)

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
    // Desktop companion marketing + release manifest (anonymous downloads)
    "/download",
    "/desktop",
    // Unlisted seed pitch deck — link-shared, not in nav, reachable anonymously
    "/deck",
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
    // First-party Google Tag Gateway (must be anonymous; browsers load /gtg without a session)
    "/gtg",
    // Playwright ExecutionResult harness (page itself 404s unless PLAYWRIGHT_E2E=1)
    "/e2e",
  ]

  const isPublicPath = publicPaths.some(
    (p) =>
      pathname === p ||
      pathname.startsWith(`${p}/`) ||
      (p !== "/" && pathname.startsWith(p))
  )

  const isApiRoute = pathname.startsWith("/api/")

  if (isPublicPath || isApiRoute) {
    return withRouteKind(supabaseResponse, pathname)
  }

  if (!user) {
    const hadSupabaseSession = request.cookies
      .getAll()
      .some((c) => c.name.startsWith("sb-") || c.name.includes("supabase-auth-token"))
    return redirectToLogin(request, { staleSession: hadSupabaseSession })
  }

  return withRouteKind(supabaseResponse, pathname)
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|css|js)$).*)",
  ],
}
