import type { IconName } from "@/lib/icons"
import { APP_ROUTES } from "@/lib/app-routes"

export const SIDEBAR_SECTION_COLORS = {
  WORK: {
    accent: "text-emerald-500",
    activeBg: "bg-emerald-500/8",
    activeBorder: "border-l-emerald-500",
    activeIcon: "text-emerald-500",
  },
  BUILD: {
    accent: "text-blue-500",
    activeBg: "bg-blue-500/8",
    activeBorder: "border-l-blue-500",
    activeIcon: "text-blue-500",
  },
  ACTIVITY: {
    accent: "text-amber-500",
    activeBg: "bg-amber-500/8",
    activeBorder: "border-l-amber-500",
    activeIcon: "text-amber-500",
  },
  INSIGHTS: {
    accent: "text-rose-500",
    activeBg: "bg-rose-500/8",
    activeBorder: "border-l-rose-500",
    activeIcon: "text-rose-500",
  },
  SETTINGS: {
    accent: "text-zinc-500",
    activeBg: "bg-zinc-500/8",
    activeBorder: "border-l-zinc-400",
    activeIcon: "text-zinc-400",
  },
} as const

export type SidebarSectionKey = keyof typeof SIDEBAR_SECTION_COLORS

export interface SidebarNavItem {
  name: string
  href: string
  icon: IconName
  badge?: string
  emphasis?: boolean
  hint?: string
}

export interface SidebarNavGroup {
  group: SidebarSectionKey
  items: SidebarNavItem[]
}

/**
 * Admin navigation after IA consolidation (~14 primary items).
 * Activity = BusinessOutcome hub; Intelligence / Settings absorb former peers.
 */
export const ADMIN_SIDEBAR_NAV: SidebarNavGroup[] = [
  {
    group: "WORK",
    items: [
      {
        name: "Getting Started",
        href: APP_ROUTES.welcome,
        icon: "rocket",
        badge: "Setup",
        emphasis: true,
        hint: "Finish setup and see progress",
      },
      { name: "Home", href: APP_ROUTES.home, icon: "home" },
      { name: "Chat", href: APP_ROUTES.gravitreAi, icon: "chat", hint: "Auto-route execute, chat, and find" },
      {
        name: "Agents",
        href: APP_ROUTES.agents,
        icon: "team",
        hint: "Roster, multi-agent runs, and training",
      },
      { name: "Assignments", href: "/assignments", icon: "clipboardList" },
      { name: "Goals", href: "/goals", icon: "target" },
    ],
  },
  {
    group: "BUILD",
    items: [
      { name: "Marketplace", href: APP_ROUTES.marketplace, icon: "package", emphasis: true },
      { name: "Workflows", href: APP_ROUTES.workflows, icon: "waypoints" },
      { name: "Connectors", href: APP_ROUTES.connectors, icon: "blocks" },
      { name: "Sources", href: "/sources", icon: "database" },
    ],
  },
  {
    group: "ACTIVITY",
    items: [
      {
        name: "Activity",
        href: APP_ROUTES.activity,
        icon: "checkCircle",
        hint: "Completed work, runs, and failure alerts",
      },
      { name: "Schedules", href: APP_ROUTES.schedules, icon: "calendar" },
      { name: "Approvals", href: APP_ROUTES.approvals, icon: "clipboardCheck" },
    ],
  },
  {
    group: "INSIGHTS",
    items: [
      {
        name: "Intelligence",
        href: APP_ROUTES.intelligence,
        icon: "sparkles",
        badge: "Explain",
        hint: "Operational health, ROI, learning, models, and memory",
      },
    ],
  },
  {
    group: "SETTINGS",
    items: [
      {
        name: "Settings",
        href: APP_ROUTES.settings,
        icon: "sliders",
        hint: "Personal, organization, and admin controls",
      },
    ],
  },
]

/** Lite navigation for end-user roles */
export const LITE_SIDEBAR_NAV: SidebarNavGroup[] = [
  {
    group: "WORK",
    items: [
      { name: "Home", href: "/lite", icon: "home", emphasis: true },
      { name: "Assign Work", href: "/lite/assign", icon: "send" },
      { name: "My Tasks", href: "/lite/tasks", icon: "listTodo" },
    ],
  },
  {
    group: "ACTIVITY",
    items: [
      { name: "Deliverables", href: "/lite/deliverables", icon: "fileText" },
      { name: "Schedules", href: APP_ROUTES.schedules, icon: "calendar" },
      { name: "Approvals", href: APP_ROUTES.approvals, icon: "clipboardCheck" },
    ],
  },
  {
    group: "INSIGHTS",
    items: [{ name: "Results", href: "/lite/results", icon: "chartLine" }],
  },
]

export function sidebarItemPath(href: string): string {
  return href.split("?")[0].split("#")[0]
}

export function isSidebarItemActive(pathname: string, href: string): boolean {
  const itemPath = sidebarItemPath(href)
  if (itemPath === "/agents") {
    return (
      pathname === "/agents" ||
      pathname.startsWith("/agents/") ||
      pathname === "/multi-agent-run" ||
      pathname.startsWith("/multi-agent-run/") ||
      pathname === "/training" ||
      pathname.startsWith("/training/")
    )
  }
  if (itemPath === "/activity") {
    return (
      pathname === "/activity" ||
      pathname.startsWith("/activity/") ||
      pathname === "/runs" ||
      pathname.startsWith("/runs/") ||
      pathname === "/outcomes" ||
      pathname.startsWith("/outcomes/") ||
      pathname.startsWith("/workflows/failure-predictions")
    )
  }
  if (itemPath === "/intelligence") {
    return (
      pathname === "/intelligence" ||
      pathname.startsWith("/intelligence/") ||
      pathname === "/metrics" ||
      pathname.startsWith("/metrics/") ||
      pathname === "/models" ||
      pathname.startsWith("/models/")
    )
  }
  if (itemPath === "/settings") {
    return (
      pathname === "/settings" ||
      pathname.startsWith("/settings/") ||
      pathname === "/environments" ||
      pathname.startsWith("/environments/") ||
      pathname === "/audit" ||
      pathname.startsWith("/audit/")
    )
  }
  return pathname === itemPath || pathname.startsWith(`${itemPath}/`)
}

/** Count of primary admin sidebar destinations (excludes Getting Started when filtered). */
export function countAdminSidebarItems(includeGettingStarted = true): number {
  return ADMIN_SIDEBAR_NAV.reduce((sum, group) => {
    return (
      sum +
      group.items.filter((item) => includeGettingStarted || item.name !== "Getting Started").length
    )
  }, 0)
}
