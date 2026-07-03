/** Canonical app routes — use these for navigation, auth redirects, and SEO. */
export const APP_ROUTES = {
  home: "/home",
  welcome: "/welcome",
  multiAgentRun: "/multi-agent-run",
  gravitreAi: "/ai",
  assistant: "/assistant",
  search: "/search",
  agents: "/agents",
  training: "/training",
  models: "/models",
  orgLearning: "/admin/intelligence",
  revenueRisk: "/admin/intelligence#revenue-risk",
  intelligence: "/intelligence",
  intelligenceAgents: "/intelligence/agents",
  intelligenceModels: "/intelligence/models",
  intelligenceMemory: "/intelligence/memory",
  intelligenceReports: "/intelligence/reports",
  marketplace: "/marketplace",
  connectors: "/connectors",
  workflows: "/workflows",
  approvals: "/approvals",
  settings: "/settings",
} as const

/** Legacy paths retained only for redirects — do not link in UI. */
export const LEGACY_APP_ROUTES = {
  operator: "/operator",
  commandCenter: "/command-center",
  agentSwarm: "/agents/swarm",
} as const

export type AppRoute = (typeof APP_ROUTES)[keyof typeof APP_ROUTES]
