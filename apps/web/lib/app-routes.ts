/** Canonical app routes — use these for navigation, auth redirects, and SEO. */
export const APP_ROUTES = {
  commandCenter: "/command-center",
  multiAgentRun: "/multi-agent-run",
  gravitreAi: "/ai",
  assistant: "/assistant",
  search: "/search",
  agents: "/agents",
  training: "/training",
  models: "/models",
  orgLearning: "/admin/intelligence",
} as const

/** Legacy paths retained only for redirects — do not link in UI. */
export const LEGACY_APP_ROUTES = {
  operator: "/operator",
  agentSwarm: "/agents/swarm",
} as const

export type AppRoute = (typeof APP_ROUTES)[keyof typeof APP_ROUTES]
