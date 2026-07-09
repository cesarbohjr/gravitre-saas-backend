/** Admin app sidebar items — keep in sync with apps/web/components/gravitre/sidebar-nav-config.ts */
export type AppNavItem = {
  name: string
  href: string
  expectedPathPrefix: string
  optional?: boolean
  hash?: string
}

export const ADMIN_APP_NAV_ITEMS: AppNavItem[] = [
  { name: "Home", href: "/home", expectedPathPrefix: "/home" },
  { name: "Chat", href: "/ai", expectedPathPrefix: "/ai" },
  { name: "Agents", href: "/agents", expectedPathPrefix: "/agents" },
  { name: "Multi-Agent Run", href: "/multi-agent-run", expectedPathPrefix: "/multi-agent-run" },
  { name: "Assignments", href: "/assignments", expectedPathPrefix: "/assignments" },
  { name: "Goals", href: "/goals", expectedPathPrefix: "/goals" },
  { name: "Marketplace", href: "/marketplace", expectedPathPrefix: "/marketplace" },
  { name: "Workflows", href: "/workflows", expectedPathPrefix: "/workflows" },
  { name: "Failure Alerts", href: "/workflows/failure-predictions", expectedPathPrefix: "/workflows/failure-predictions" },
  { name: "Training", href: "/training", expectedPathPrefix: "/training" },
  { name: "Models", href: "/models", expectedPathPrefix: "/models" },
  { name: "Connectors", href: "/connectors", expectedPathPrefix: "/connectors" },
  { name: "Sources", href: "/sources", expectedPathPrefix: "/sources" },
  { name: "Runs", href: "/runs", expectedPathPrefix: "/runs" },
  { name: "Schedules", href: "/schedules", expectedPathPrefix: "/schedules" },
  { name: "Approvals", href: "/approvals", expectedPathPrefix: "/approvals" },
  { name: "Metrics", href: "/metrics", expectedPathPrefix: "/metrics" },
  { name: "Insights", href: "/intelligence", expectedPathPrefix: "/intelligence" },
  { name: "Agent profiles", href: "/intelligence/agents", expectedPathPrefix: "/intelligence/agents" },
  { name: "Built-in models", href: "/models/built-in", expectedPathPrefix: "/models/built-in" },
  { name: "Memory", href: "/intelligence/memory", expectedPathPrefix: "/intelligence/memory" },
  { name: "Reports", href: "/intelligence/reports", expectedPathPrefix: "/intelligence/reports" },
  {
    name: "Revenue risk",
    href: "/intelligence/learning#revenue-risk",
    expectedPathPrefix: "/intelligence/learning",
    hash: "#revenue-risk",
  },
  { name: "Learning", href: "/intelligence/learning", expectedPathPrefix: "/intelligence/learning" },
  { name: "History", href: "/audit", expectedPathPrefix: "/audit" },
  { name: "Environments", href: "/environments", expectedPathPrefix: "/environments" },
  { name: "Enterprise", href: "/settings/enterprise", expectedPathPrefix: "/settings/enterprise" },
  { name: "Federation", href: "/settings/federation", expectedPathPrefix: "/settings/federation" },
  { name: "Settings", href: "/settings", expectedPathPrefix: "/settings" },
]
