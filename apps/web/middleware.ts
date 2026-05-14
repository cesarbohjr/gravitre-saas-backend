import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

const CANONICAL_REDIRECT_ROUTES = [
  "/login",
  "/get-started",
  "/forgot-password",
  "/auth/callback",
  "/operator",
  "/onboarding",
]
const CANONICAL_AUTH_ORIGIN = "https://gravitre.app"

// Routes that don't require authentication
const PUBLIC_ROUTES = [
  "/",
  "/login",
  "/get-started",
  "/forgot-password",
  "/auth/callback",
  // Product
  "/features",
  "/pricing",
  "/changelog",
  "/roadmap",
  // Company
  "/about",
  "/blog",
  "/careers",
  "/contact",
  // Help
  "/docs",
  "/api",
  "/guides",
  "/support",
  // Legal
  "/privacy",
  "/terms",
  "/security",
]

// Static asset patterns to ignore
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

  // Skip middleware for static files and API routes
  if (STATIC_PATTERNS.some((pattern) => pathname.startsWith(pattern))) {
    return NextResponse.next()
  }

  if (
    CANONICAL_REDIRECT_ROUTES.some(
      (route) => pathname === route || pathname.startsWith(`${route}/`),
    )
  ) {
    const isLocalhost = request.nextUrl.hostname === "localhost" || request.nextUrl.hostname === "127.0.0.1"
    if (!isLocalhost) {
      const canonicalUrl = new URL(CANONICAL_AUTH_ORIGIN)
      if (request.nextUrl.host !== canonicalUrl.host) {
        const redirectUrl = new URL(
          `${pathname}${request.nextUrl.search}`,
          canonicalUrl,
        )
        return NextResponse.redirect(redirectUrl)
      }
    }
  }

  // Allow public routes
  if (PUBLIC_ROUTES.some((route) => pathname === route || pathname.startsWith(route + "/"))) {
    return NextResponse.next()
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
