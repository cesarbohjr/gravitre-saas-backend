import { createServerClient } from "@supabase/ssr"
import { NextResponse, type NextRequest } from "next/server"

export async function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname

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

  // CRITICAL: getUser() validates with Supabase — never getSession() here.
  const {
    data: { user },
  } = await supabase.auth.getUser()

  const publicPaths = [
    "/",
    "/login",
    "/get-started",
    "/auth",
    "/pricing",
    "/features",
    "/about",
    "/docs",
    "/forgot-password",
    "/privacy",
    "/terms",
    "/security",
    "/api/auth",
    "/_next",
    "/favicon",
    "/robots.txt",
    "/sitemap",
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
    const loginUrl = new URL("/login", request.url)
    const hasSupabaseCookie = request.cookies
      .getAll()
      .some(
        (c) =>
          c.name.startsWith("sb-") || c.name.includes("supabase-auth-token")
      )

    if (hasSupabaseCookie) {
      loginUrl.searchParams.set("error", "session_expired")
    }

    return NextResponse.redirect(loginUrl)
  }

  return supabaseResponse
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|css|js)$).*)",
  ],
}
