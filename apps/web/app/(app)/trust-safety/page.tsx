"use client"

import { Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
import { TrustSafetyApprovals } from "@/components/trust-safety/trust-safety-approvals"
import { TrustSafetyAudit } from "@/components/trust-safety/trust-safety-audit"
import { TrustSafetyPolicies } from "@/components/trust-safety/trust-safety-policies"
import "./gv-trust.css"

type Tab = "approvals" | "audit" | "policies"

const CRUMB: Record<Tab, string> = {
  approvals: "Approvals",
  audit: "Audit trail",
  policies: "Policies",
}
const HEADING: Record<Tab, string> = {
  approvals: "Approvals",
  audit: "Audit trail",
  policies: "Policies",
}
const LEDE: Record<Tab, string> = {
  approvals: "Review and decide on every agent action that paused for a human.",
  audit: "Who did what, when, and how it turned out. Filter by actor and outcome, then export.",
  policies: "Guardrails applied to every agent, workflow and chat write in this workspace.",
}

function TrustSafetyContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const raw = searchParams.get("tab") as Tab | null
  const tab: Tab = raw === "audit" || raw === "policies" ? raw : "approvals"

  const go = (next: Tab) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set("tab", next)
    router.replace(`/trust-safety?${params.toString()}`)
  }

  const navCls = (t: Tab) => `gv-sl${tab === t ? " on" : ""}`
  const tabCls = (t: Tab) => `gv-tab${tab === t ? " on" : ""}`

  return (
    <div style={{ maxWidth: 1400, margin: "0 auto", padding: "24px 24px 96px", display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 32, alignItems: "flex-start" }}>

        {/* ── Left sidebar nav ──────────────────────────────────────── */}
        <aside className="gv-snav" aria-label="Trust and Safety">
          <div className="gv-shead" style={{ padding: "0 4px" }}>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600, letterSpacing: "-0.01em" }}>Trust &amp; Safety</h1>
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "#6A6B64" }}>Approvals, audit and governance</p>
          </div>

          <nav style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <div className="gv-sgrp">Review</div>
              <button type="button" className={navCls("approvals")} aria-current={tab === "approvals" ? "page" : undefined} onClick={() => go("approvals")}>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5" /><path d="m8.5 12 2.5 2.5 4.5-5" /></svg>
                Approvals
                <span className="gv-count" />
              </button>
              <button type="button" className={navCls("audit")} aria-current={tab === "audit" ? "page" : undefined} onClick={() => go("audit")}>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M9 6h11M9 12h11M9 18h11" /><path d="m3.5 6 1 1 2-2M3.5 12l1 1 2-2M3.5 18l1 1 2-2" /></svg>
                Audit trail
              </button>
            </div>

            <div>
              <div className="gv-sgrp">Controls</div>
              <button type="button" className={navCls("policies")} aria-current={tab === "policies" ? "page" : undefined} onClick={() => go("policies")}>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6z" /><path d="m9 12 2 2 4-4" /></svg>
                Policies
              </button>
            </div>

            <div>
              <div className="gv-sgrp">Related settings</div>
              <button type="button" className="gv-sl">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="4.5" y="10" width="15" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>
                Security
              </button>
              <button type="button" className="gv-sl">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c1-3.5 3.5-5.5 6.5-5.5s5.5 2 6.5 5.5" /><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14.8c1.8.8 3 2.6 3.5 5.2" /></svg>
                Role permissions
              </button>
              <button type="button" className="gv-sl">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="4" y="4" width="16" height="7" rx="2" /><rect x="4" y="13" width="16" height="7" rx="2" /><path d="M8 7.5h.01M8 16.5h.01" /></svg>
                Environments
              </button>
            </div>
          </nav>

          <div className="gv-note gv-shead" style={{ margin: "0 4px" }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0B8A5C" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ flex: "0 0 auto", marginTop: 2 }}><circle cx="12" cy="12" r="8.5" /><path d="M12 11v5M12 8h.01" /></svg>
            <span>Every decision and policy change here is written to the audit trail.</span>
          </div>
        </aside>

        {/* ── Main content area ─────────────────────────────────────── */}
        <div style={{ flex: "1 1 600px", minWidth: 0, display: "flex", flexDirection: "column", gap: 20 }}>

          {/* Breadcrumb + heading + action row */}
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 16 }}>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 13, color: "#6A6B64" }}>Trust &amp; Safety / {CRUMB[tab]}</div>
              <h2 style={{ margin: "6px 0 0", fontSize: 32, lineHeight: 1.1, fontWeight: 600, letterSpacing: "-0.02em" }}>{HEADING[tab]}</h2>
              <p style={{ margin: "8px 0 0", fontSize: 15, color: "#55564F", maxWidth: 640, lineHeight: 1.5 }}>{LEDE[tab]}</p>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, color: "#55564F" }}>
                <span className="gv-dot gv-live" style={{ background: "#19C37D" }} />
                Live
              </span>
              <button type="button" className="gv-btn line sm">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 4v11M7 10l5 5 5-5M5 20h14" /></svg>
                Export report
              </button>
              <button type="button" className="gv-btn green sm" onClick={() => go("policies")}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
                New policy
              </button>
            </div>
          </div>

          {/* Tab strip */}
          <div className="gv-tabs" role="tablist" aria-label="Trust and Safety sections" style={{ alignSelf: "flex-start" }}>
            <button type="button" role="tab" className={tabCls("approvals")} aria-selected={tab === "approvals"} onClick={() => go("approvals")}>
              Approvals
            </button>
            <button type="button" role="tab" className={tabCls("audit")} aria-selected={tab === "audit"} onClick={() => go("audit")}>
              Audit trail
            </button>
            <button type="button" role="tab" className={tabCls("policies")} aria-selected={tab === "policies"} onClick={() => go("policies")}>
              Policies
            </button>
          </div>

          {/* Tab panels */}
          {tab === "approvals" && (
            <div role="tabpanel" aria-label="Approvals">
              <TrustSafetyApprovals />
            </div>
          )}
          {tab === "audit" && (
            <div role="tabpanel" aria-label="Audit trail">
              <TrustSafetyAudit />
            </div>
          )}
          {tab === "policies" && (
            <div role="tabpanel" aria-label="Policies">
              <TrustSafetyPolicies />
            </div>
          )}

        </div>
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
