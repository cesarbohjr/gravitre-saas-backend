/** Admin app sidebar items — keep in sync with ADMIN_SIDEBAR_NAV in apps/web/components/gravitre/sidebar-nav-config.ts */
export type AppNavItem = {
  name: string
  href: string
  expectedPathPrefix: string
  optional?: boolean
  hash?: string
}

export const ADMIN_APP_NAV_ITEMS: AppNavItem[] = [
  { name: "Getting Started", href: "/welcome", expectedPathPrefix: "/welcome", optional: true },
  { name: "Home", href: "/home", expectedPathPrefix: "/home" },
  { name: "Chat", href: "/ai", expectedPathPrefix: "/ai" },
  { name: "Agents", href: "/agents", expectedPathPrefix: "/agents" },
  { name: "Assignments", href: "/assignments", expectedPathPrefix: "/assignments" },
  { name: "Goals", href: "/goals", expectedPathPrefix: "/goals" },
  { name: "Marketplace", href: "/marketplace/assets", expectedPathPrefix: "/marketplace" },
  { name: "Workflows", href: "/workflows", expectedPathPrefix: "/workflows" },
  { name: "Connectors", href: "/connectors", expectedPathPrefix: "/connectors" },
  { name: "Sources", href: "/sources", expectedPathPrefix: "/sources" },
  { name: "Activity", href: "/activity", expectedPathPrefix: "/activity" },
  { name: "Schedules", href: "/schedules", expectedPathPrefix: "/schedules" },
  { name: "Approvals", href: "/approvals", expectedPathPrefix: "/approvals" },
  { name: "Deliverables", href: "/lite/deliverables", expectedPathPrefix: "/lite/deliverables", optional: true },
  { name: "Intelligence", href: "/intelligence", expectedPathPrefix: "/intelligence" },
  { name: "Results", href: "/lite/results", expectedPathPrefix: "/lite/results", optional: true },
  { name: "Settings", href: "/settings", expectedPathPrefix: "/settings" },
]
