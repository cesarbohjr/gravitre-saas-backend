/**
 * Group-level route access classification for anonymous browser requests.
 * Keep these roots in sync with app/(app) and app/(marketing).
 * CI's check-route-root-access.mjs fails if new directories are not classified.
 */
export const PRIVATE_ROUTE_ROOTS = [
  "activity", "admin", "agents", "ai", "approvals", "assignments", "audit",
  "chat", "connectors", "environments", "goals", "home", "intelligence",
  "lite", "marketplace", "metrics", "models", "multi-agent-run",
  "notifications", "objectives", "platform", "plays", "runs", "schedules",
  "search", "settings", "sources", "training", "workflows",
] as const

export const PUBLIC_MARKETING_ROUTE_ROOTS = [
  "about", "api", "blog", "careers", "changelog", "contact", "docs",
  "download", "features", "forgot-password", "get-started", "guides",
  "login", "pricing", "privacy", "roadmap", "security", "support", "terms",
] as const

/** Product routes outside the app route group; never inadvertently public. */
export const OTHER_PRIVATE_ROUTE_ROOTS = [
  "assistant", "deliverables", "extension", "integrations", "onboarding",
  "operator", "outcomes", "systems", "tasks", "welcome",
] as const

const privateRoots = new Set<string>([...PRIVATE_ROUTE_ROOTS, ...OTHER_PRIVATE_ROUTE_ROOTS])
const marketingRoots = new Set<string>(PUBLIC_MARKETING_ROUTE_ROOTS)

export function classifyTopLevelRoute(pathname: string): "private" | "marketing" | "unknown" {
  const segment = pathname.split("/").filter(Boolean)[0]
  if (!segment) return "marketing"
  if (privateRoots.has(segment)) return "private"
  if (marketingRoots.has(segment)) return "marketing"
  return "unknown"
}
