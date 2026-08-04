"use client"

import { usePathname, useSearchParams } from "next/navigation"
import { HubTabs, type HubTabItem } from "@/components/gravitre/hub-tabs"

export type AgentsHubTab = "roster" | "multi-agent" | "training"

const TABS: Array<HubTabItem<AgentsHubTab>> = [
  { id: "roster", label: "Roster", href: "/agents" },
  { id: "multi-agent", label: "Multi-agent", href: "/multi-agent-run" },
  { id: "training", label: "Training", href: "/training" },
]

export function resolveAgentsHubTab(pathname: string, tabParam: string | null): AgentsHubTab {
  if (pathname.startsWith("/multi-agent-run")) return "multi-agent"
  if (pathname.startsWith("/training")) return "training"
  if (tabParam === "multi-agent") return "multi-agent"
  if (tabParam === "training") return "training"
  return "roster"
}

export function AgentsHubTabs({ active }: { active?: AgentsHubTab }) {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const current = active ?? resolveAgentsHubTab(pathname, searchParams.get("tab"))

  return <HubTabs tabs={TABS} active={current} ariaLabel="Agents hub" className="mb-4" />
}
