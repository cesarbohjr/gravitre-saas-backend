"use client"

import { BarChart3, DollarSign, Globe, Palette, Shield } from "lucide-react"
import { cn } from "@/lib/utils"
import type { EnterpriseTabId } from "./types"

const tabs: { id: EnterpriseTabId; label: string; icon: typeof Globe }[] = [
  { id: "region", label: "Data Region", icon: Globe },
  { id: "branding", label: "Branding", icon: Palette },
  { id: "analytics", label: "Workforce", icon: BarChart3 },
  { id: "cost", label: "Cost", icon: DollarSign },
  { id: "siem", label: "SIEM", icon: Shield },
]

interface EnterpriseSubNavProps {
  activeTab: EnterpriseTabId
  onTabChange: (tab: EnterpriseTabId) => void
}

export function EnterpriseSubNav({ activeTab, onTabChange }: EnterpriseSubNavProps) {
  return (
    <>
      <nav className="hidden w-48 shrink-0 flex-col gap-1 md:flex">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => onTabChange(tab.id)}
            className={cn(
              "flex items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors",
              activeTab === tab.id
                ? "bg-accent text-accent-foreground font-medium"
                : "text-muted-foreground hover:bg-secondary hover:text-foreground"
            )}
          >
            <tab.icon className="h-4 w-4 shrink-0" />
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="flex gap-1 overflow-x-auto rounded-lg border border-border bg-secondary/30 p-1 md:hidden">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => onTabChange(tab.id)}
            className={cn(
              "inline-flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs transition-colors",
              activeTab === tab.id
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground"
            )}
          >
            <tab.icon className="h-3.5 w-3.5" />
            {tab.label}
          </button>
        ))}
      </div>
    </>
  )
}
