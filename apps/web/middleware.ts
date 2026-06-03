import { createServerClient } from "@supabase/ssr"
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

  let supabaseResponse = NextResponse.next({
    request,
  })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          )
          supabaseResponse = NextResponse.next({
            request,
          })
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  const {
    data: { user },
  } = await supabase.auth.getUser()

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

  if (pathname.startsWith("/auth/callback")) {
    return supabaseResponse
  }

  const isPublic =
    pathname === "/" ||
    [
      "/login",
      "/get-started",
      "/auth/",
      "/api/",
      "/_next/",
      "/favicon",
      "/robots",
      "/sitemap",
      "/pricing",
      "/about",
      "/features",
      "/forgot-password",
      "/privacy",
      "/terms",
      "/security",
      "/docs",
    ].some((p) => pathname.startsWith(p))

  if (isPublic) {
    return supabaseResponse
  }

  if (!user) {
    const loginUrl = new URL("/login", request.url)
    const hadSession = request.cookies
      .getAll()
      .some((c) => c.name.includes("supabase"))

    if (hadSession) {
      loginUrl.searchParams.set("error", "session_expired")
    }
    return NextResponse.redirect(loginUrl)
  }

  return supabaseResponse
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
}
