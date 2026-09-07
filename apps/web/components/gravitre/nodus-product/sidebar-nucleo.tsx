/**
 * Sidebar IconName → Nucleo semantic component where a purchased glyph exists.
 * Unmapped names keep Lucide via `<Icon />` until more Nucleo assets are vendored.
 */
import type { ComponentType, SVGProps } from "react"
import type { IconName } from "@/lib/icons"
import {
  NucleoAgent,
  NucleoApproval,
  NucleoClose,
  NucleoConnector,
  NucleoIntelligence,
  NucleoMenu,
  NucleoSearch,
  NucleoWorkflow,
} from "@/components/icons/nucleo/semantic"

type NucleoNavIcon = ComponentType<SVGProps<SVGSVGElement> & { className?: string; size?: number | string }>

export const SIDEBAR_NUCLEO_BY_ICON: Partial<Record<IconName, NucleoNavIcon>> = {
  team: NucleoAgent,
  agents: NucleoAgent,
  blocks: NucleoConnector,
  apps: NucleoConnector,
  waypoints: NucleoWorkflow,
  workflows: NucleoWorkflow,
  clipboardCheck: NucleoApproval,
  approvals: NucleoApproval,
  sparkles: NucleoIntelligence,
  brain: NucleoIntelligence,
  close: NucleoClose,
  menu: NucleoMenu,
  search: NucleoSearch,
}

export function resolveSidebarNavIcon(name: IconName): NucleoNavIcon | null {
  return SIDEBAR_NUCLEO_BY_ICON[name] ?? null
}
