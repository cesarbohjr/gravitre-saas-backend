/**
 * Anonymous marketing / content routes (app/(marketing) + login/get-started).
 * Keep in sync with `publicPaths` in proxy.ts — minus auth, API, gtg, e2e, desktop.
 */
const MARKETING_EXACT = new Set([
  "/",
  "/login",
  "/get-started",
  "/pricing",
  "/about",
  "/contact",
  "/careers",
  "/changelog",
  "/guides",
  "/roadmap",
  "/support",
  "/download",
  "/forgot-password",
  "/privacy",
  "/terms",
  "/security",
  "/api", // marketing /api page (not /api/* backend routes)
])

const MARKETING_PREFIXES = [
  "/features",
  "/docs",
  "/blog",
] as const

export function isMarketingContentRoute(pathname: string): boolean {
  if (!pathname) return false
  if (MARKETING_EXACT.has(pathname)) return true
  if (pathname.startsWith("/api/")) return false
  return MARKETING_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`))
}
