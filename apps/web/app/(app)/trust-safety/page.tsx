"use client"

import { Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
import { cn } from "@/lib/utils"

// Lazy-load the three tab bodies to keep the initial bundle small.
// Each page already exists as a standalone route; we re-use its content here.
import { TrustSafetyApprovals } from "@/components/trust-safety/trust-safety-approvals"
import { TrustSafetyAudit } from "@/components/trust-safety/trust-safety-audit"
import { TrustSafetyPolicies } from "@/components/trust-safety/trust-safety-policies"

type Tab = "approvals" | "audit" | "policies"

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "approvals", label: "Approvals" },
  { id: "audit", label: "Audit Trail" },
  { id: "policies", label: "Policies" },
]

function TrustSafetyContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const raw = searchParams.get("tab") as Tab | null
  const tab: Tab = raw && TABS.some((t) => t.id === raw) ? raw : "approvals"

  const setTab = (next: Tab) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set("tab", next)
    router.replace(`/trust-safety?${params.toString()}`)
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Tab bar */}
      <div
        role="tablist"
        aria-label="Trust &amp; Safety sections"
        className="flex shrink-0 gap-1 border-b border-[color:var(--g-border-default)] px-4 md:px-6"
      >
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            aria-controls={`trust-panel-${id}`}
            id={`trust-tab-${id}`}
            type="button"
            onClick={() => setTab(id)}
            className={cn(
              "relative -mb-px pb-3 pt-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              tab === id
                ? "border-b-2 border-[color:var(--g-brand)] text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab panels */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div
          role="tabpanel"
          id="trust-panel-approvals"
          aria-labelledby="trust-tab-approvals"
          hidden={tab !== "approvals"}
        >
          {tab === "approvals" && <TrustSafetyApprovals />}
        </div>
        <div
          role="tabpanel"
          id="trust-panel-audit"
          aria-labelledby="trust-tab-audit"
          hidden={tab !== "audit"}
        >
          {tab === "audit" && <TrustSafetyAudit />}
        </div>
        <div
          role="tabpanel"
          id="trust-panel-policies"
          aria-labelledby="trust-tab-policies"
          hidden={tab !== "policies"}
        >
          {tab === "policies" && <TrustSafetyPolicies />}
        </div>
      </div>
    </div>
  )
}

export default function TrustSafetyPage() {
  return (
    <AppShell title="Trust &amp; Safety" fillViewport>
      <Suspense fallback={null}>
        <TrustSafetyContent />
      </Suspense>
    </AppShell>
  )
}
