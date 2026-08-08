import type { IconName } from "@/lib/icons"
import { APP_ROUTES } from "@/lib/app-routes"

/**
 * Sidebar sections share a single brand accent (`--primary`) plus neutrals.
 *
 * Sections used to each carry their own hue (emerald / blue / amber / rose /
 * zinc), which made the rail read as decoration rather than wayfinding and
 * blew past a 3-5 color system. Grouping is now communicated structurally —
 * uppercase section labels, dividers, and spacing — so the accent is reserved
 * for the one thing that matters: which item is active.
 *
 * The per-section map is retained so callers can keep passing `colors`, and so
 * a section can opt into a different treatment later without touching links.
 */
const SIDEBAR_ACCENT = {
  accent: "text-primary",
  activeBg: "bg-primary/10",
  activeBorder: "border-l-primary",
  activeIcon: "text-primary",
} as const

export const SIDEBAR_SECTION_COLORS = {
  WORK: SIDEBAR_ACCENT,
  BUILD: SIDEBAR_ACCENT,
  ACTIVITY: SIDEBAR_ACCENT,
  INSIGHTS: SIDEBAR_ACCENT,
  SETTINGS: SIDEBAR_ACCENT,
} as const

export type SidebarSectionKey = keyof typeof SIDEBAR_SECTION_COLORS

export interface SidebarNavItem {
  name: string
  href: string
  icon: IconName
  badge?: string
  emphasis?: boolean
  hint?: string
  /** A1: BUILD surfaces — full seat only; Lite sees locked affordance on shared nav. */
  requiresFullSeat?: boolean
  /** Shown for Lite seats (and admins previewing Lite) on the shared shell. */
  liteWork?: boolean
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
      {
        name: "Marketplace",
        href: APP_ROUTES.marketplace,
        icon: "package",
        emphasis: true,
        requiresFullSeat: true,
        hint: "Requires a full seat",
      },
      {
        name: "Workflows",
        href: APP_ROUTES.workflows,
        icon: "waypoints",
        requiresFullSeat: true,
        hint: "Requires a full seat — Lite can run department-assigned workflows",
      },
      {
        name: "Connectors",
        href: APP_ROUTES.connectors,
        icon: "blocks",
        requiresFullSeat: true,
        hint: "Requires a full seat",
      },
      {
        name: "Sources",
        href: "/sources",
        icon: "database",
        requiresFullSeat: true,
        hint: "Requires a full seat",
      },
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
      {
        name: "Deliverables",
        href: "/lite/deliverables",
        icon: "fileText",
        liteWork: true,
        hint: "Outputs from your assigned work",
      },
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
      {
        name: "Results",
        href: "/lite/results",
        icon: "chartLine",
        liteWork: true,
        hint: "Your department results",
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

/** Seat-scoped WORK items injected into the shared shell when seat is Lite. */
export const LITE_WORK_NAV_ITEMS: SidebarNavItem[] = [
  { name: "Assign Work", href: "/lite/assign", icon: "send", liteWork: true },
  { name: "My Tasks", href: "/lite/tasks", icon: "listTodo", liteWork: true },
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
