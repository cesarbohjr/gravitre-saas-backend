"use client"

import Link from "next/link"
import { usePathname, useSearchParams } from "next/navigation"
import { cn } from "@/lib/utils"
import { HUB_TABS } from "@/lib/design-system"

export type AgentsHubTab = "roster" | "multi-agent" | "training"

const LINKS: Array<{ id: AgentsHubTab; label: string; href: string }> = [
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

export function AgentsHubTabs({
  active,
  inHeader = false,
}: {
  active?: AgentsHubTab
  /** Inside a page header that owns the bottom border. */
  inHeader?: boolean
}) {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const current = active ?? resolveAgentsHubTab(pathname, searchParams.get("tab"))

  return (
    <nav
      aria-label="Agents hub"
      className={cn(HUB_TABS.nav, !inHeader && "mb-0 border-b border-[color:var(--g-border-subtle)]")}
    >
      {LINKS.map((link) => {
        const isActive = current === link.id
        return (
          <Link
            key={link.id}
            href={link.href}
            aria-current={isActive ? "page" : undefined}
            className={cn(HUB_TABS.link, isActive ? HUB_TABS.active : HUB_TABS.idle)}
          >
            {link.label}
          </Link>
        )
      })}
    </nav>
  )
}
