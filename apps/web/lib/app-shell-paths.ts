/**
 * Paths that should NOT mount the authenticated AppShell.
 * Everything else under the web app gets a persistent shell from AppShellGate
 * so the sidebar survives client navigations.
 */
const APP_SHELL_EXCLUDED_PREFIXES = [
  "/login",
  "/get-started",
  "/forgot-password",
  "/auth",
  "/welcome",
  "/onboarding",
  "/lite",
  "/api",
  "/e2e",
  // Marketing (route group (marketing) — keep shell off these surfaces)
  "/features",
  "/pricing",
  "/docs",
  "/blog",
  "/about",
  "/contact",
  "/security",
  "/support",
  "/changelog",
  "/guides",
  "/terms",
  "/privacy",
  "/careers",
  "/roadmap",
  // Standalone authenticated surfaces with their own chrome
  "/settings/organizations",
  // Legacy redirects (no UI chrome needed)
  "/deliverables",
  "/operator",
  "/assistant",
  "/tasks",
  "/systems",
] as const

export function shouldMountAppShell(pathname: string | null | undefined): boolean {
  if (!pathname) return false
  if (pathname === "/") return false
  return !APP_SHELL_EXCLUDED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  )
}
