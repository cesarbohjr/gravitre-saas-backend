import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

const CANONICAL_HOST = "gravitre.app"
const CANONICAL_ORIGIN = `https://${CANONICAL_HOST}`

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

  const hostname = request.nextUrl.hostname.toLowerCase()
  const isLocalhost = hostname === "localhost" || hostname === "127.0.0.1"
  const isCanonicalHost = hostname === CANONICAL_HOST || hostname.endsWith(`.${CANONICAL_HOST}`)

  // Enforce canonical host for all browser routes so users never see Vercel URLs.
  if (!isLocalhost && !isCanonicalHost) {
    const redirectUrl = new URL(`${pathname}${request.nextUrl.search}`, CANONICAL_ORIGIN)
    return NextResponse.redirect(redirectUrl)
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
