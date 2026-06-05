import { type NextRequest } from "next/server"

import { redirectToLogin, updateSession } from "@/lib/supabase/middleware"

export async function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname

  const { response: supabaseResponse, user } = await updateSession(request)

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
