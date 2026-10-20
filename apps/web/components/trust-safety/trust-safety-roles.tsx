"use client"

import { useState } from "react"

const ROLE_CARDS = [
  {
    name: "Admin",
    desc: "Full workspace control including billing, members and all settings.",
    count: 2,
    color: "#2B59E0",
    bg: "#E8EEFC",
  },
  {
    name: "Member",
    desc: "Can create agents, run workflows and view intelligence dashboards.",
    count: 14,
    color: "#0B8A5C",
    bg: "#EAF7F0",
  },
  {
    name: "Viewer",
    desc: "Read-only access to dashboards and agent run history.",
    count: 5,
    color: "#6A6B64",
    bg: "#F2F2EE",
  },
]

const CAPS: [string, string, [number, number, number]][] = [
  ["Insights", "View dashboards and intelligence", [1, 1, 1]],
  ["Insights", "Run Gravitre AI and chat", [1, 1, 1]],
  ["Build", "Create agents and workflows", [1, 1, 0]],
  ["Build", "Install marketplace packs", [1, 0, 0]],
  ["Build", "Manage connectors", [1, 1, 0]],
  ["Govern", "Review and decide approvals", [1, 1, 0]],
  ["Govern", "Configure policies", [1, 0, 0]],
  ["Govern", "View audit trail", [1, 1, 1]],
  ["Settings", "Manage members and roles", [1, 0, 0]],
  ["Settings", "Billing and subscriptions", [1, 0, 0]],
  ["Settings", "Security settings", [1, 0, 0]],
]

type View = "matrix" | "role"

export function TrustSafetyRoles() {
  const [view, setView] = useState<View>("matrix")
  const [role, setRole] = useState(0)

  const cur = ROLE_CARDS[role]

  // Group caps by category for single-role view
  const grouped: Record<string, typeof CAPS> = {}
  for (const cap of CAPS) {
    if (!grouped[cap[0]]) grouped[cap[0]] = []
    grouped[cap[0]].push(cap)
  }

  return (
    <div className="gv-rise" style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* ── Hero tiles ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(200px,1fr))", gap: 12 }}>
        {ROLE_CARDS.map((rc, i) => (
          <button
            key={rc.name}
            type="button"
            className={`gv-wcard${view === "role" && role === i ? " sel" : ""}`}
            style={{
              border: `1.5px solid ${view === "role" && role === i ? rc.color : "#E4E4DF"}`,
              borderRadius: 14,
              padding: "16px 18px",
              background: view === "role" && role === i ? rc.bg : "#FFFFFF",
              textAlign: "left",
              cursor: "pointer",
              display: "flex",
              flexDirection: "column",
              gap: 8,
              transition: "border-color .15s,background .15s",
            }}
            onClick={() => { setRole(i); setView("role") }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: rc.color }}>{rc.name}</span>
              <span style={{ fontFamily: "'Geist Mono',monospace", fontSize: 11, color: "#6A6B64" }}>{rc.count} members</span>
            </div>
            <p style={{ margin: 0, fontSize: 13, color: "#55564F", lineHeight: 1.45 }}>{rc.desc}</p>
          </button>
        ))}
      </div>

      {/* ── View toggle ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <div className="gv-tabs" style={{ alignSelf: "flex-start" }}>
          <button
            type="button"
            className={`gv-tab${view === "matrix" ? " on" : ""}`}
            onClick={() => setView("matrix")}
          >
            Compare all roles
          </button>
          <button
            type="button"
            className={`gv-tab${view === "role" ? " on" : ""}`}
            onClick={() => setView("role")}
          >
            {cur.name} detail
          </button>
        </div>
        {view === "role" && (
          <div style={{ display: "flex", gap: 6 }}>
            {ROLE_CARDS.map((rc, i) => (
              <button
                key={rc.name}
                type="button"
                className={`gv-chip${role === i ? " on" : ""}`}
                style={role === i ? { borderColor: rc.color, background: rc.bg, color: rc.color } : {}}
                onClick={() => setRole(i)}
              >
                {rc.name}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Matrix view ── */}
      {view === "matrix" && (
        <div className="gv-card gv-tblwrap">
          <div style={{ minWidth: 560 }}>
            {/* Header */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr repeat(3,80px)", padding: "12px 20px", borderBottom: "1px solid #EFEFEA" }}>
              <span className="gv-th">Capability</span>
              {ROLE_CARDS.map(rc => (
                <span key={rc.name} className="gv-th" style={{ textAlign: "center", color: rc.color }}>{rc.name}</span>
              ))}
            </div>
            {/* Group separator + rows */}
            {(() => {
              let lastGroup = ""
              return CAPS.map(([grp, cap, perms], idx) => {
                const showHeader = grp !== lastGroup
                lastGroup = grp
                return (
                  <div key={idx}>
                    {showHeader && (
                      <div style={{ padding: "10px 20px 4px", fontSize: 11, fontFamily: "'Geist Mono',monospace", letterSpacing: ".1em", textTransform: "uppercase", color: "#6A6B64", background: "#FAFAF8", borderTop: idx > 0 ? "1px solid #EFEFEA" : undefined }}>
                        {grp}
                      </div>
                    )}
                    <div className="gv-row" style={{ display: "grid", gridTemplateColumns: "1fr repeat(3,80px)", padding: "0 20px" }}>
                      <span className="gv-td" style={{ fontSize: 13, color: "#3E3F3A" }}>{cap}</span>
                      {perms.map((p, pi) => (
                        <span key={pi} className="gv-td" style={{ textAlign: "center" }}>
                          {p ? (
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={ROLE_CARDS[pi].color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-label="Yes"><circle cx="12" cy="12" r="8.5" /><path d="m8.5 12 2.5 2.5 4.5-5" /></svg>
                          ) : (
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#D9D9D3" strokeWidth="2" strokeLinecap="round" aria-label="No"><path d="M6 18 18 6M6 6l12 12" /></svg>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                )
              })
            })()}
          </div>
        </div>
      )}

      {/* ── Single-role view ── */}
      {view === "role" && (
        <div className="gv-card" style={{ overflow: "hidden" }}>
          <div style={{ padding: "20px 20px 0", borderBottom: "1px solid #EFEFEA" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, paddingBottom: 16 }}>
              <div className="gv-ico" style={{ background: cur.bg, color: cur.color }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c1-3.5 3.5-5.5 6.5-5.5s5.5 2 6.5 5.5" /><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14.8c1.8.8 3 2.6 3.5 5.2" /></svg>
              </div>
              <div>
                <div style={{ fontSize: 16, fontWeight: 700, color: cur.color }}>{cur.name}</div>
                <div style={{ fontSize: 13, color: "#6A6B64" }}>{cur.desc}</div>
              </div>
              <div style={{ marginLeft: "auto", textAlign: "right" }}>
                <div style={{ fontFamily: "'Geist Mono',monospace", fontSize: 22, fontWeight: 700, color: "#141513" }}>{cur.count}</div>
                <div style={{ fontSize: 12, color: "#6A6B64" }}>members</div>
              </div>
            </div>
          </div>

          {Object.entries(grouped).map(([grp, caps]) => (
            <div key={grp}>
              <div style={{ padding: "12px 20px 4px", fontSize: 11, fontFamily: "'Geist Mono',monospace", letterSpacing: ".1em", textTransform: "uppercase", color: "#6A6B64", background: "#FAFAF8", borderTop: "1px solid #EFEFEA" }}>
                {grp}
              </div>
              {caps.map(([, cap, perms]) => {
                const allowed = perms[role] === 1
                return (
                  <div key={cap} className="gv-row" style={{ display: "flex", alignItems: "center", gap: 14, padding: "0 20px" }}>
                    <span className="gv-td" style={{ flex: 1, fontSize: 13, color: "#3E3F3A" }}>{cap}</span>
                    <span className="gv-td" style={{ flexShrink: 0 }}>
                      {allowed ? (
                        <span className="gv-pill" style={{ background: "#EAF7F0", color: "#0B8A5C" }}>Allowed</span>
                      ) : (
                        <span className="gv-pill" style={{ background: "#F2F2EE", color: "#6A6B64" }}>Not allowed</span>
                      )}
                    </span>
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
