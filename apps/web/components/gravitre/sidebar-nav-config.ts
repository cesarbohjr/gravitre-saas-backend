import type { IconName } from "@/lib/icons"
import { APP_ROUTES } from "@/lib/app-routes"
import { SURFACE_COPY } from "@/lib/surface-copy"

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

/** Admin navigation — Think → Automate → Activity → Understand → Govern */
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
      { name: "Agents", href: APP_ROUTES.agents, icon: "team" },
      { name: "Multi-Agent Run", href: APP_ROUTES.multiAgentRun, icon: "network" },
      { name: "Assignments", href: "/assignments", icon: "clipboardList" },
      { name: "Goals", href: "/goals", icon: "target" },
    ],
  },
  {
    group: "BUILD",
    items: [
      { name: "Marketplace", href: APP_ROUTES.marketplace, icon: "package", emphasis: true },
      { name: "Workflows", href: APP_ROUTES.workflows, icon: "waypoints" },
      { name: "Failure Alerts", href: "/workflows/failure-predictions", icon: "shieldAlert" },
      { name: SURFACE_COPY.training.title, href: APP_ROUTES.training, icon: "brain" },
      { name: SURFACE_COPY.models.title, href: APP_ROUTES.models, icon: "cpu" },
      { name: "Connectors", href: APP_ROUTES.connectors, icon: "blocks" },
      { name: "Sources", href: "/sources", icon: "database" },
    ],
  },
  {
    group: "ACTIVITY",
    items: [
      { name: "Runs", href: "/runs", icon: "listTodo" },
      { name: "Schedules", href: "/schedules", icon: "calendar" },
      { name: "Approvals", href: APP_ROUTES.approvals, icon: "clipboardCheck" },
    ],
  },
  {
    group: "INSIGHTS",
    items: [
      { name: "Metrics", href: "/metrics", icon: "layoutDashboard" },
      {
        name: SURFACE_COPY.insights.title,
        href: APP_ROUTES.intelligence,
        icon: "sparkles",
        badge: "Explain",
        hint: "Observed outcomes, confidence, and recommendations",
      },
      { name: SURFACE_COPY.hubLinks.agents.title, href: APP_ROUTES.intelligenceAgents, icon: "team" },
      { name: SURFACE_COPY.builtInModels.title, href: APP_ROUTES.builtInModels, icon: "cpu" },
      { name: SURFACE_COPY.hubLinks.memory.title, href: APP_ROUTES.intelligenceMemory, icon: "database" },
      { name: SURFACE_COPY.hubLinks.reports.title, href: APP_ROUTES.intelligenceReports, icon: "chartLine" },
      {
        name: "Revenue risk",
        href: APP_ROUTES.revenueRisk,
        icon: "shieldAlert",
        hint: "Pipeline and revenue signals needing review",
      },
      {
        name: SURFACE_COPY.learning.title,
        href: APP_ROUTES.learning,
        icon: "atom",
        hint: "Query, memory, and search learning",
      },
      { name: "Audit trail", href: "/audit", icon: "history", hint: "Who did what, when — compliance and review" },
    ],
  },
  {
    group: "SETTINGS",
    items: [
      { name: "Environments", href: "/environments", icon: "boxes" },
      { name: "Enterprise", href: "/settings/enterprise", icon: "building" },
      { name: "Federation", href: "/settings/federation", icon: "handshake" },
      { name: "Settings", href: "/settings", icon: "sliders" },
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
      { name: "Schedules", href: "/schedules", icon: "calendar" },
      { name: "Approvals", href: "/approvals", icon: "clipboardCheck" },
    ],
  },
  {
    group: "INSIGHTS",
    items: [{ name: "Results", href: "/lite/results", icon: "chartLine" }],
  },
]

export function sidebarItemPath(href: string): string {
  return href.split("#")[0]
}

export function isSidebarItemActive(pathname: string, href: string): boolean {
  const itemPath = sidebarItemPath(href)
  return pathname === itemPath || pathname.startsWith(`${itemPath}/`)
}
