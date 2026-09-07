/**
 * Sidebar IconName → sharp Nodus-style outline glyphs.
 * Unmapped names fall back to `<Icon />` (Lucide / existing Nucleo).
 */
import type { ComponentType, SVGProps } from "react"
import type { IconName } from "@/lib/icons"
import {
  NavActivity,
  NavAgent,
  NavApproval,
  NavCalendar,
  NavChart,
  NavChat,
  NavDatabase,
  NavFile,
  NavGrid,
  NavPackage,
  NavPlug,
  NavRocket,
  NavSliders,
  NavSparkles,
  NavTarget,
  NavTasks,
  NavWorkflow,
} from "@/components/icons/nodus-nav/outline"

type NavIcon = ComponentType<SVGProps<SVGSVGElement> & { className?: string; size?: number | string }>

export const SIDEBAR_NUCLEO_BY_ICON: Partial<Record<IconName, NavIcon>> = {
  home: NavGrid,
  layoutGrid: NavGrid,
  grid: NavGrid,
  team: NavAgent,
  agents: NavAgent,
  blocks: NavPlug,
  apps: NavPlug,
  connectors: NavPlug,
  waypoints: NavWorkflow,
  workflows: NavWorkflow,
  clipboardList: NavTasks,
  listTodo: NavTasks,
  clipboardCheck: NavApproval,
  approvals: NavApproval,
  sparkles: NavSparkles,
  brain: NavSparkles,
  chat: NavChat,
  target: NavTarget,
  database: NavDatabase,
  calendar: NavCalendar,
  checkCircle: NavActivity,
  package: NavPackage,
  fileText: NavFile,
  chartLine: NavChart,
  sliders: NavSliders,
  rocket: NavRocket,
}

export function resolveSidebarNavIcon(name: IconName): NavIcon | null {
  return SIDEBAR_NUCLEO_BY_ICON[name] ?? null
}
