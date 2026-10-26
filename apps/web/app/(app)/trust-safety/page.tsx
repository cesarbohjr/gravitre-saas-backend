"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { toast } from "@/components/agents/overlays/toast"
import { AppShell } from "@/components/gravitre/app-shell"
import { exportAudit, rangeStart } from "@/lib/settings-api/audit"
import { Icon, type IconName } from "@/components/trust-safety/ts-ui"
import { TrustSafetyApprovals, useApprovalCounts } from "@/components/trust-safety/trust-safety-approvals"
import { TrustSafetyAudit, useAuditTotals } from "@/components/trust-safety/trust-safety-audit"
import { TrustSafetyPolicies, usePolicyState } from "@/components/trust-safety/trust-safety-policies"
import { TrustSafetySecurity, useSecurityState } from "@/components/trust-safety/trust-safety-security"
import { TrustSafetyRoles } from "@/components/trust-safety/trust-safety-roles"
import { TrustSafetyEnvironments } from "@/components/trust-safety/trust-safety-environments"
import "./gv-trust.css"

type Tab = "approvals" | "audit" | "policies" | "security" | "roles" | "envs"

const ALL_TABS: Tab[] = ["approvals", "audit", "policies", "security", "roles", "envs"]

function updatedLabel(at: number | null, now: number): string {
  if (at == null) return "Live"
  const mins = Math.floor(Math.max(0, now - at) / 60_000)
  if (mins < 1) return "Live · updated just now"
  if (mins < 60) return `Live · updated ${mins} min ago`
  return `Live · updated ${Math.floor(mins / 60)} h ago`
}

function TrustSafetyContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const raw = searchParams.get("tab") as Tab | null
  const tab: Tab = raw && ALL_TABS.includes(raw) ? raw : "approvals"

  const approvals = useApprovalCounts()
  const audit = useAuditTotals()
  const policy = usePolicyState()
  const security = useSecurityState()

  const [now, setNow] = useState(() => Date.now())
  const [exporting, setExporting] = useState(false)
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])

  const go = (next: Tab) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set("tab", next)
    router.replace(`/trust-safety?${params.toString()}`, { scroll: false })
  }

  const exportReport = async () => {
    if (exporting) return
    setExporting(true)
    try {
      const response = await exportAudit("csv", { range: "7d" }, rangeStart("7d"))
      if (!response.ok) throw new Error(`Export failed (${response.status})`)
      const url = URL.createObjectURL(await response.blob())
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = "trust-safety-report-7d.csv"
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
      toast.success("Report exported")
    } catch {
      toast.error("Could not export the report")
    } finally {
      setExporting(false)
    }
  }

  const tabBtn = (id: Tab, icon: IconName, label: string, count?: { text: string; bad?: boolean } | null) => (
    <button type="button" role="tab" className={`ts-tab${tab === id ? " on" : ""}`} aria-selected={tab === id} onClick={() => go(id)}>
      <Icon name={icon} size={15} />
      {label}
      {count ? <span className={`ts-tn${count.bad ? " bad" : ""}`}>{count.text}</span> : null}
    </button>
  )

  return (
    <div className="ts-root">
      <div style={{ maxWidth: 1240, margin: "0 auto", padding: "28px 24px 104px", display: "flex", flexDirection: "column", gap: 22 }}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 16 }}>
          <div style={{ minWidth: 0 }}>
            <div className="ts-eyebrow">Governance</div>
            <h1 style={{ margin: "6px 0 0", fontSize: 34, lineHeight: 1.1, fontWeight: 600, letterSpacing: "-0.02em" }}>Trust &amp; Safety</h1>
            <p style={{ margin: "8px 0 0", fontSize: 15, color: "#55564F", maxWidth: 640, lineHeight: 1.5 }}>
              Review what agents ask to do, trace what happened, and set the controls that keep people and agents inside safe limits.
            </p>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, color: "#55564F", border: "1px solid #E4E4DF", background: "#FFFFFF", borderRadius: 999, padding: "6px 12px" }}>
              <span className="ts-dot ts-live" style={{ background: "#19C37D" }} />
              {updatedLabel(approvals.updatedAt, now)}
            </span>
            <button type="button" className="ts-btn line sm" onClick={exportReport} disabled={exporting}>
              <Icon name="download" size={15} />
              {exporting ? "Exporting…" : "Export report"}
            </button>
          </div>
        </div>

        <nav className="ts-tabbar" aria-label="Trust and Safety sections">
          <div className="ts-tgrp">
            <span className="ts-tlabel">Review</span>
            <div className="ts-tabs" role="tablist" aria-label="Review">
              {tabBtn("approvals", "check", "Approvals", approvals.waiting == null ? null : { text: String(approvals.waiting) })}
              {tabBtn("audit", "list", "Audit trail", audit.errors ? { text: audit.errors.toLocaleString(), bad: true } : null)}
            </div>
          </div>
          <div className="ts-tgrp">
            <span className="ts-tlabel">Controls</span>
            <div className="ts-tabs" role="tablist" aria-label="Controls">
              {tabBtn("policies", "shieldCheck", "Policies", { text: `${policy.on ?? "–"}/4` })}
              {tabBtn("security", "lock", "Security", { text: `${security.score}/4` })}
              {tabBtn("roles", "users", "Role permissions")}
              {tabBtn("envs", "servers", "Environments")}
            </div>
          </div>
        </nav>

        {tab === "approvals" && <TrustSafetyApprovals onViewPast={() => go("audit")} />}
        {tab === "audit" && <TrustSafetyAudit />}
        {tab === "policies" && <TrustSafetyPolicies state={policy} onOpenAudit={() => go("audit")} />}
        {tab === "security" && <TrustSafetySecurity state={security} />}
        {tab === "roles" && <TrustSafetyRoles />}
        {tab === "envs" && <TrustSafetyEnvironments />}
      </div>
    </div>
  )
}

export default function TrustSafetyPage() {
  return (
    <AppShell title="Trust &amp; Safety">
      <Suspense fallback={null}>
        <TrustSafetyContent />
      </Suspense>
    </AppShell>
  )
}
