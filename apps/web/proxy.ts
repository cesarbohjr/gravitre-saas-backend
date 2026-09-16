import { NextResponse, type NextRequest } from "next/server"

import { clickupRootOAuthRedirect } from "@/lib/clickup-oauth-callback"
import { usesMarketingProviderTree } from "@/lib/is-marketing-route"
import { redirectToLogin, updateSession } from "@/lib/supabase/middleware"

function withRouteKind(
  response: NextResponse,
  request: NextRequest,
  pathname: string,
): NextResponse {
  // Shared with MarketingProviders' mismatch guard — see
  // usesMarketingProviderTree for why the two must not drift.
  const isMarketing = usesMarketingProviderTree(pathname)

  const requestHeaders = new Headers(request.headers)
  requestHeaders.set("x-pathname", pathname)
  if (isMarketing) {
    requestHeaders.set("x-gravitre-marketing", "1")
  }

  const enriched = NextResponse.next({
    request: { headers: requestHeaders },
  })

  response.cookies.getAll().forEach((cookie) => {
    enriched.cookies.set(cookie.name, cookie.value, cookie)
  })

  enriched.headers.set("x-pathname", pathname)
  if (isMarketing) {
    enriched.headers.set("x-gravitre-marketing", "1")
  }

  return enriched
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
    return withRouteKind(supabaseResponse, request, pathname)
  }

  if (!user) {
    const oauthReturn = request.nextUrl.searchParams.get("oauth")
    // Connector Google OAuth shares the login GCP client. Returning from consent
    // can briefly fail getUser(); wiping cookies turns that into a logout loop.
    if (
      pathname.startsWith("/connectors") &&
      (oauthReturn === "success" || oauthReturn === "error")
    ) {
      return withRouteKind(supabaseResponse, request, pathname)
    }
    const hadSupabaseSession = request.cookies
      .getAll()
      .some((c) => c.name.startsWith("sb-") || c.name.includes("supabase-auth-token"))
    return redirectToLogin(request, { staleSession: hadSupabaseSession })
  }

  return withRouteKind(supabaseResponse, request, pathname)
}

export const config = {
  matcher: [
    // NOTE: `avif` was missing here — any .avif asset (e.g. the homepage/about
    // dashboard screenshot) was falling through to auth-gating and 307'ing
    // anonymous visitors to /login instead of serving the static image.
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|avif|ico|css|js)$).*)",
  ],
}
