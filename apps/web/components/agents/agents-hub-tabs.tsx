"use client"

import Link from "next/link"
import { usePathname, useSearchParams } from "next/navigation"
import { cn } from "@/lib/utils"

export type AgentsHubTab = "roster" | "multi-agent" | "training"

const TABS: Array<{ id: AgentsHubTab; label: string; href: string }> = [
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

  return (
    <div
      className="mb-4 flex flex-wrap gap-1 rounded-lg border border-border bg-muted/30 p-1"
      role="tablist"
      aria-label="Agents hub"
    >
      {TABS.map((tab) => {
        const selected = current === tab.id
        return (
          <Link
            key={tab.id}
            href={tab.href}
            role="tab"
            aria-selected={selected}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              selected
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {tab.label}
          </Link>
        )
      })}
    </div>
  )
}
