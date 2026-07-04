/** Canonical app routes — use these for navigation, auth redirects, and SEO. */
export const APP_ROUTES = {
  home: "/home",
  welcome: "/welcome",
  multiAgentRun: "/multi-agent-run",
  gravitreAi: "/ai",
  /** Workspace chat mode on the unified AI surface */
  gravitreAiChat: "/ai?mode=chat",
  universalSearch: "/search",
  agents: "/agents",
  training: "/training",
  models: "/models",
  orgLearning: "/admin/intelligence",
  revenueRisk: "/admin/intelligence#revenue-risk",
  intelligence: "/intelligence",
  intelligenceAgents: "/intelligence/agents",
  intelligenceModels: "/intelligence/models",
  intelligencePredictive: "/intelligence/predictive",
  intelligenceMemory: "/intelligence/memory",
  intelligenceReports: "/intelligence/reports",
  marketplace: "/marketplace",
  connectors: "/connectors",
  workflows: "/workflows",
  runs: "/runs",
  approvals: "/approvals",
  settings: "/settings",
} as const

/** Legacy paths retained only for redirects — do not link in UI. */
export const LEGACY_APP_ROUTES = {
  operator: "/operator",
  commandCenter: "/command-center",
  agentSwarm: "/agents/swarm",
  assistant: "/assistant",
  chat: "/chat",
  tasks: "/tasks",
  systems: "/systems",
} as const

export type AppRoute = (typeof APP_ROUTES)[keyof typeof APP_ROUTES]
