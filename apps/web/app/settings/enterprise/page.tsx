"use client"

import { useState, useEffect, Suspense } from "react"
import { useSearchParams, useRouter, usePathname } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
import { PageHeader } from "@/components/gravitre/page-header"
import { useAuth } from "@/lib/auth-context"
import { cn } from "@/lib/utils"
import { Globe, Palette, Users, DollarSign, ShieldAlert, Lock, HeartPulse } from "lucide-react"
import { RegionTab } from "@/components/enterprise/region-tab"
import { BrandingTab } from "@/components/enterprise/branding-tab"
import { WorkforceTab } from "@/components/enterprise/workforce-tab"
import { CostTab } from "@/components/enterprise/cost-tab"
import { SiemTab } from "@/components/enterprise/siem-tab"
import { CsDashboardTab } from "@/components/enterprise/cs-dashboard-tab"

type TabId = "cs" | "region" | "branding" | "workforce" | "cost" | "siem"

const TABS: { id: TabId; label: string; icon: typeof Globe; description: string }[] = [
  { id: "cs", label: "Command Center", icon: HeartPulse, description: "Integration health and recommendations" },
  { id: "region", label: "Data Residency", icon: Globe, description: "Control where your data is stored" },
  { id: "branding", label: "White Label", icon: Palette, description: "Custom logo, color, and domain" },
  { id: "workforce", label: "Workforce", icon: Users, description: "Agent task analytics" },
  { id: "cost", label: "Cost Attribution", icon: DollarSign, description: "Spend by agent and department" },
  { id: "siem", label: "SIEM Export", icon: ShieldAlert, description: "Stream audit logs to your SIEM" },
]

const TAB_IDS = TABS.map((t) => t.id)

export default function EnterprisePage() {
  return (
    <Suspense fallback={null}>
      <EnterprisePageContent />
    </Suspense>
  )
}

function EnterprisePageContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const pathname = usePathname()
  const tabParam = searchParams.get("tab")
  const initialTab: TabId = TAB_IDS.includes(tabParam as TabId) ? (tabParam as TabId) : "cs"
  const [activeTab, setActiveTab] = useState<TabId>(initialTab)
  const { user, loading } = useAuth()

  // Keep state in sync if the URL param changes (e.g. deep links from suggestions).
  useEffect(() => {
    if (tabParam && TAB_IDS.includes(tabParam as TabId) && tabParam !== activeTab) {
      setActiveTab(tabParam as TabId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tabParam])

  const selectTab = (id: TabId) => {
    setActiveTab(id)
    const params = new URLSearchParams(Array.from(searchParams.entries()))
    params.set("tab", id)
    router.replace(`${pathname}?${params.toString()}`, { scroll: false })
  }

  const role = user?.role
  const isAdmin = role === "admin" || role === "owner"

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-6xl px-4 py-6 md:px-6 md:py-8">
        <PageHeader
          title="Enterprise"
          description="Advanced controls for data residency, white labeling, workforce analytics, and security."
        />

        {!loading && !isAdmin ? (
          <div className="mt-8 flex flex-col items-center justify-center rounded-lg border border-border bg-card px-6 py-16 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
              <Lock className="h-6 w-6 text-muted-foreground" aria-hidden="true" />
            </div>
            <h2 className="mt-4 text-lg font-semibold text-foreground">Admin access required</h2>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground text-pretty">
              Enterprise settings are only available to workspace owners and admins. Contact your administrator if you
              need access.
            </p>
          </div>
        ) : (
          <div className="mt-6 flex flex-col gap-6 lg:flex-row lg:gap-8">
            {/* Sub navigation */}
            <nav aria-label="Enterprise settings" className="lg:w-64 lg:shrink-0">
              {/* Mobile: horizontal scroll. Desktop: vertical list */}
              <div className="flex gap-2 overflow-x-auto pb-2 lg:flex-col lg:gap-1 lg:overflow-visible lg:pb-0">
                {TABS.map((tab) => {
                  const Icon = tab.icon
                  const active = activeTab === tab.id
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => selectTab(tab.id)}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex shrink-0 items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors lg:w-full",
                        active
                          ? "border-primary/30 bg-primary/10 text-foreground"
                          : "border-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
                      )}
                    >
                      <Icon
                        className={cn("h-4 w-4 shrink-0", active ? "text-primary" : "text-muted-foreground")}
                        aria-hidden="true"
                      />
                      <span className="flex flex-col">
                        <span className="text-sm font-medium leading-tight">{tab.label}</span>
                        <span className="hidden text-xs text-muted-foreground lg:block">{tab.description}</span>
                      </span>
                    </button>
                  )
                })}
              </div>
            </nav>

            {/* Tab content */}
            <div className="min-w-0 flex-1">
              {activeTab === "cs" && <CsDashboardTab />}
              {activeTab === "region" && <RegionTab isAdmin={isAdmin} />}
              {activeTab === "branding" && <BrandingTab isAdmin={isAdmin} />}
              {activeTab === "workforce" && <WorkforceTab />}
              {activeTab === "cost" && <CostTab />}
              {activeTab === "siem" && <SiemTab isAdmin={isAdmin} />}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
