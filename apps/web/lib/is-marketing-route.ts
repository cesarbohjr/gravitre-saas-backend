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

/**
 * The unlisted /deck presentation is a standalone surface routed through the
 * lighter marketing provider tree so the operator AI helper / app shell is not
 * mounted over the slides. Kept out of `isMarketingContentRoute` so it stays
 * absent from the sitemap and remains noindex.
 */
function isDeckRoute(pathname: string): boolean {
  return pathname === "/deck" || pathname.startsWith("/deck/")
}

/**
 * Whether a path is served by `MarketingProviders` rather than `AppProviders`.
 *
 * Single source of truth, consumed by both `proxy.ts` (which sets the
 * `x-gravitre-marketing` request header) and `MarketingProviders` (which has to
 * detect when it is mounted on a path that needs the operator tree). If these
 * two ever disagree, the guard in `MarketingProviders` would either miss a real
 * mismatch or reload forever on a legitimately-marketing path.
 */
export function usesMarketingProviderTree(pathname: string): boolean {
  if (!pathname) return false
  return isMarketingContentRoute(pathname) || isDeckRoute(pathname)
}
