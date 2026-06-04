import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

// IMPORTANT — Auth model:
// This middleware does NOT enforce authentication. The app authenticates with a
// client-side Supabase session (browser) and sends Bearer tokens to the API,
// where access is enforced by backend JWT verification + Supabase RLS. Protected
// pages are gated client-side (auth-context / AppShell). The only job of this
// middleware is to canonicalize the host for auth-sensitive routes so users never
// see a raw deployment URL (e.g. *.up.railway.app) in the address bar.

// Routes that should ALWAYS redirect to the canonical domain (NEXT_PUBLIC_APP_URL)
// to prevent users from landing on a non-canonical deployment host.
const CANONICAL_REDIRECT_ROUTES = [
  "/login",
  "/get-started",
  "/forgot-password",
  "/auth/callback",
  "/operator",
  "/onboarding",
]

// Paths the middleware never touches (static assets + API).
const STATIC_PATTERNS = [
  "/_next",
  "/api",
  "/images",
  "/favicon",
  "/robots.txt",
  "/sitemap.xml",
]

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  if (STATIC_PATTERNS.some((pattern) => pathname.startsWith(pattern))) {
    return NextResponse.next()
  }

  const canonicalAppUrl = (process.env.NEXT_PUBLIC_APP_URL || "").trim()
  if (
    canonicalAppUrl &&
    CANONICAL_REDIRECT_ROUTES.some(
      (route) => pathname === route || pathname.startsWith(`${route}/`),
    )
  ) {
    try {
      const canonicalUrl = new URL(canonicalAppUrl)
      if (request.nextUrl.host !== canonicalUrl.host) {
        const redirectUrl = new URL(
          `${pathname}${request.nextUrl.search}`,
          canonicalUrl,
        )
        return NextResponse.redirect(redirectUrl)
      }
    } catch {
      // Ignore malformed NEXT_PUBLIC_APP_URL and continue request handling.
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
}
