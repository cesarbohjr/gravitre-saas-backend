"use client"

import { useState } from "react"

const STAGES = [
  {
    id: "dev",
    label: "Development",
    short: "Dev",
    status: "healthy",
    agents: 3,
    runs: 142,
    uptime: "99.8%",
    lastDeploy: "2 min ago",
    desc: "Sandbox for building and testing agents before promoting to staging. Changes here do not affect live workflows.",
    color: "#2B59E0",
    bg: "#E8EEFC",
  },
  {
    id: "staging",
    label: "Staging",
    short: "Staging",
    status: "healthy",
    agents: 2,
    runs: 89,
    uptime: "99.5%",
    lastDeploy: "1 h ago",
    desc: "Pre-production mirror of live connectors. QA and stakeholder review happen here before agents go live.",
    color: "#D08A00",
    bg: "#FBF1DC",
  },
  {
    id: "prod",
    label: "Production",
    short: "Prod",
    status: "healthy",
    agents: 2,
    runs: 1204,
    uptime: "99.97%",
    lastDeploy: "3 d ago",
    desc: "Live environment processing real customer data. All approvals and policies are enforced here.",
    color: "#0B8A5C",
    bg: "#EAF7F0",
  },
]

const METRICS = [
  { label: "Runs today", vals: [142, 89, 1204] },
  { label: "Uptime", vals: ["99.8%", "99.5%", "99.97%"] },
  { label: "Avg. latency", vals: ["340 ms", "280 ms", "210 ms"] },
  { label: "Error rate", vals: ["0.4%", "0.2%", "0.03%"] },
]

export function TrustSafetyEnvironments() {
  const [sel, setSel] = useState(0)
  const [promo, setPromo] = useState(false)

  const env = STAGES[sel]

  return (
    <div className="gv-rise" style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* ── Pipeline strip ── */}
      <div className="gv-card" style={{ padding: 28 }}>
        <div style={{ fontSize: 11, fontFamily: "'Geist Mono',monospace", letterSpacing: ".12em", textTransform: "uppercase", color: "#6A6B64", marginBottom: 16 }}>
          Deployment pipeline
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 0, overflowX: "auto" }}>
          {STAGES.map((s, i) => (
            <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 0, flex: i < STAGES.length - 1 ? "1 1 0" : undefined }}>
              <button
                type="button"
                onClick={() => setSel(i)}
                style={{
                  border: `2px solid ${sel === i ? s.color : "#E4E4DF"}`,
                  borderRadius: 14,
                  padding: "14px 20px",
                  background: sel === i ? s.bg : "#FAFAF8",
                  cursor: "pointer",
                  textAlign: "left",
                  minWidth: 130,
                  transition: "border-color .15s,background .15s",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <span className="gv-dot" style={{ background: "#19C37D" }} />
                  <span style={{ fontSize: 12, fontWeight: 700, color: sel === i ? s.color : "#141513" }}>{s.short}</span>
                </div>
                <div style={{ fontFamily: "'Geist Mono',monospace", fontSize: 18, fontWeight: 700, color: sel === i ? s.color : "#141513" }}>
                  {s.agents}
                </div>
                <div style={{ fontSize: 11, color: "#8A8B85" }}>agents</div>
              </button>

              {i < STAGES.length - 1 && (
                <div style={{ flex: 1, display: "flex", alignItems: "center", padding: "0 4px", position: "relative", minWidth: 40 }}>
                  <div style={{ flex: 1, borderTop: "2px dashed #D9D9D3" }} />
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="#D9D9D3" style={{ flexShrink: 0 }}>
                    <path d="M8 4l8 8-8 8" fill="none" stroke="#D9D9D3" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── Detail panel ── */}
      <div className="gv-card" style={{ overflow: "hidden" }}>
        <div style={{ padding: "20px 24px", borderBottom: "1px solid #EFEFEA", display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <div className="gv-ico" style={{ background: env.bg, color: env.color }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4" width="16" height="7" rx="2" /><rect x="4" y="13" width="16" height="7" rx="2" /><path d="M8 7.5h.01M8 16.5h.01" /></svg>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: env.color }}>{env.label}</div>
            <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2 }}>{env.desc}</div>
          </div>
          <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
            <span className="gv-pill" style={{ background: "#EAF7F0", color: "#0B8A5C", fontSize: 12 }}>
              <span className="gv-dot gv-live" style={{ background: "#19C37D" }} />
              {env.status}
            </span>
            <span style={{ fontSize: 12, color: "#8A8B85" }}>Last deploy: {env.lastDeploy}</span>
          </div>
        </div>

        {/* Metrics grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(150px,1fr))", gap: 1, background: "#EFEFEA", borderBottom: "1px solid #EFEFEA" }}>
          {METRICS.map((m) => (
            <div key={m.label} style={{ background: "#FFFFFF", padding: "16px 20px" }}>
              <div style={{ fontSize: 11, fontFamily: "'Geist Mono',monospace", letterSpacing: ".1em", textTransform: "uppercase", color: "#6A6B64", marginBottom: 4 }}>{m.label}</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: "#141513", letterSpacing: "-0.02em" }}>
                {String(m.vals[sel])}
              </div>
            </div>
          ))}
        </div>

        {/* Promotion toggle */}
        {sel < STAGES.length - 1 && (
          <div className="gv-sec">
            <div className="gv-ico" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 4v16M4 12l8-8 8 8" /></svg>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#141513" }}>
                Promote to {STAGES[sel + 1].label}
              </div>
              <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2 }}>
                Auto-promote agents when all checks pass in {env.label}. Requires approval from a member with Admin role.
              </div>
            </div>
            <button
              type="button"
              className={`gv-sw${promo ? " on" : ""}`}
              aria-pressed={promo}
              aria-label={`Toggle auto-promote to ${STAGES[sel + 1].label}`}
              onClick={() => setPromo(!promo)}
            />
          </div>
        )}
        {promo && sel < STAGES.length - 1 && (
          <div style={{ margin: "0 20px 20px", marginLeft: 72 }}>
            <div className="gv-note">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0B8A5C" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ flex: "0 0 auto", marginTop: 2 }}><circle cx="12" cy="12" r="8.5" /><path d="M12 11v5M12 8h.01" /></svg>
              <span>
                Agents passing all checks in <strong>{env.label}</strong> will automatically be promoted to <strong>{STAGES[sel + 1].label}</strong>. An Admin must approve each promotion before it goes live.
              </span>
            </div>
          </div>
        )}

        {/* Manual promote action (only dev→staging, staging→prod) */}
        {sel < STAGES.length - 1 && (
          <div style={{ padding: "16px 24px", borderTop: "1px solid #EFEFEA", display: "flex", gap: 10 }}>
            <button type="button" className="gv-btn green sm">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 4v16M4 12l8-8 8 8" /></svg>
              Promote to {STAGES[sel + 1].label}
            </button>
            <button type="button" className="gv-btn line sm">View diff</button>
          </div>
        )}
      </div>

      {/* Stage navigation pills */}
      <div style={{ display: "flex", gap: 6 }}>
        {STAGES.map((s, i) => (
          <button
            key={s.id}
            type="button"
            className={`gv-chip${sel === i ? " on" : ""}`}
            style={sel === i ? { borderColor: s.color, background: s.bg, color: s.color } : {}}
            onClick={() => setSel(i)}
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  )
}
