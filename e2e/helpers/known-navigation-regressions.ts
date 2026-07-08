/** Manual QA regressions — must pass via real browser clicks, not fetch-only checks. */
export const KNOWN_NAVIGATION_REGRESSIONS = [
  {
    id: "support-getting-started",
    sourcePath: "/support",
    linkText: "Getting Started",
    expectedPathPrefix: "/docs/getting-started",
    note: "Was /support/getting-started 404",
  },
  {
    id: "guides-first-agent",
    sourcePath: "/guides",
    linkText: "Create Your First AI Agent",
    expectedPathPrefix: "/docs/guides/how-to/agents",
    note: "Was /guides/create-your-first-ai-agent 404",
  },
  {
    id: "support-popular-first-agent",
    sourcePath: "/support",
    linkText: "How to create your first agent",
    expectedPathPrefix: "/docs/guides/how-to/agents",
    note: "Was /docs/guides/how-to-create-your-first-agent empty stub",
  },
] as const

export const METADATA_PAGES = [
  { path: "/api", titleFragment: "API" },
  { path: "/support", titleFragment: "Support" },
  { path: "/changelog", titleFragment: "Changelog" },
] as const

export const HOMEPAGE_DEFAULT_TITLE = "Gravitre — AI operations with GIBE"

export const HUB_PAGES = ["/docs", "/guides", "/support"] as const
