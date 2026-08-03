/** Canonical app routes — use these for navigation, auth redirects, and SEO. */
export const APP_ROUTES = {
  home: "/home",
  welcome: "/welcome",
  /** Multi-agent deep-link (Agents hub tab — not primary nav) */
  multiAgentRun: "/multi-agent-run",
  gravitreAi: "/ai",
  /** Workspace chat mode on the unified AI surface */
  gravitreAiChat: "/ai?mode=chat",
  universalSearch: "/search",
  agents: "/agents",
  /** Training deep-link (Agents hub tab — not primary nav) */
  training: "/training",
  /** Model registry — Intelligence hub section (page remains at /models) */
  models: "/models",
  /** Org-wide learning from usage (Observe step) — Intelligence section */
  learning: "/intelligence/learning",
  builtInModels: "/models/built-in",
  /** @deprecated use learning */
  orgLearning: "/intelligence/learning",
  revenueRisk: "/intelligence/learning#revenue-risk",
  intelligence: "/intelligence",
  /** @deprecated merged into Agents hub */
  intelligenceAgents: "/agents",
  /** @deprecated use builtInModels */
  intelligenceModels: "/models/built-in",
  intelligencePredictive: "/intelligence/predictive",
  intelligenceMemory: "/intelligence/memory",
  intelligenceReports: "/intelligence/reports",
  marketplace: "/marketplace/assets",
  connectors: "/connectors",
  workflows: "/workflows",
  /** Canonical execution hub (BusinessOutcome + failure alerts) */
  activity: "/activity",
  /**
   * Run detail base path (`/runs/[id]`). List view redirects to Activity —
   * do not use this for top-level nav; use `activity`.
   */
  runs: "/runs",
  /** @deprecated use activity — redirect stub only */
  outcomes: "/activity",
  approvals: "/approvals",
  settings: "/settings",
  schedules: "/schedules",
  audit: "/audit",
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
  adminIntelligence: "/admin/intelligence",
  intelligenceModelsPath: "/intelligence/models",
  runsList: "/runs",
  outcomesList: "/outcomes",
  metrics: "/metrics",
  multiAgentRunPage: "/multi-agent-run",
  trainingPage: "/training",
  failureAlerts: "/workflows/failure-predictions",
  intelligenceAgentsList: "/intelligence/agents",
  marketplaceRoi: "/marketplace/analytics/roi",
} as const

export type AppRoute = (typeof APP_ROUTES)[keyof typeof APP_ROUTES]
