/**
 * G-STRUCT A1 page families (approved 2026-09-24): Operating / Expert / Empty /
 * Immersive. The shell reads the family from the route so composition, chrome
 * density and the AI dock placement differ by job instead of every route sharing
 * one header → tabs → white canvas pattern. "Empty" is a state inside a family,
 * not a route class, so it is not resolved here.
 */
export type PageFamily = "operating" | "expert" | "immersive" | "standard"

/** Help is a scrollable document, even though it lives under the chat URL. */
export function isAiHelpRoute(pathname: string): boolean {
  return /^\/ai\/help(?:\/|$)/.test(pathname.split("?")[0] ?? "")
}

/** Conversation surfaces exclude the help documents beneath the same URL. */
export function isAiConversationRoute(pathname: string): boolean {
  const path = pathname.split("?")[0] ?? ""
  return (path === "/ai" || path.startsWith("/ai/")) && !isAiHelpRoute(path)
}

const IMMERSIVE: RegExp[] = [
  /^\/ai(\/|$)/,
  /^\/agents\/[^/]+\/chat\/?$/,
  /^\/workflows\/[^/]+\/builder(\/|$)/,
  /^\/multi-agent-run(\/|$)/,
]

const EXPERT: RegExp[] = [
  /^\/intelligence(\/|$)/,
  /^\/models(\/|$)/,
  /^\/metrics(\/|$)/,
  /^\/agents\/(?!new(\/|$))[^/]+(\/|$)/,
  /^\/connectors(\/|$)/,
  /^\/sources\/[^/]+(\/|$)/,
  /^\/admin(\/|$)/,
  /^\/training(\/|$)/,
]

const OPERATING: RegExp[] = [
  /^\/home\/?$/,
  /^\/dashboard\/?$/,
  /^\/agents\/?$/,
  /^\/workflows\/?$/,
  /^\/assignments(\/|$)/,
  /^\/approvals(\/|$)/,
  /^\/activity(\/|$)/,
  /^\/runs(\/|$)/,
  /^\/goals(\/|$)/,
  /^\/schedules(\/|$)/,
  /^\/sources\/?$/,
  /^\/notifications(\/|$)/,
  /^\/outcomes(\/|$)/,
]

export function resolvePageFamily(pathname: string): PageFamily {
  const path = (pathname.split("?")[0] ?? "").replace(/\/+$/, "") || "/"
  if (isAiHelpRoute(path)) return "standard"
  if (IMMERSIVE.some((re) => re.test(path))) return "immersive"
  if (EXPERT.some((re) => re.test(path))) return "expert"
  if (OPERATING.some((re) => re.test(path))) return "operating"
  return "standard"
}

/** Immersive surfaces own their chrome: the global top bar steps aside. */
export function familyHidesTopBar(pathname: string): boolean {
  const path = pathname.split("?")[0] ?? ""
  return /^\/workflows\/[^/]+\/builder(\/|$)/.test(path)
}
