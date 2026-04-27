import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

const AUTH_PAGES = ["/login", "/signup", "/get-started"]
const PROTECTED_PREFIXES = [
  "/operator",
  "/agents",
  "/workflows",
  "/runs",
  "/approvals",
  "/connectors",
  "/sources",
  "/metrics",
  "/settings",
  "/training",
  "/lite",
  "/audit",
]

function hasAuthCookie(request: NextRequest): boolean {
  const cookieNames = request.cookies.getAll().map((item) => item.name)
  return cookieNames.some((name) => name.startsWith("sb-") || name.includes("supabase"))
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl
  const authenticated = hasAuthCookie(request)

  if (AUTH_PAGES.some((page) => pathname.startsWith(page)) && authenticated) {
    return NextResponse.redirect(new URL("/operator", request.url))
  }

  const needsAuth = PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix))
  if (needsAuth && !authenticated) {
    const loginUrl = new URL("/login", request.url)
    loginUrl.searchParams.set("next", pathname)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
}
