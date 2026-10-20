"use client"

import { Fragment, useState } from "react"
import { Hero, Icon, Note, Pill, Switch, TONE } from "./ts-ui"

type StageId = "dev" | "stage" | "prod"

const STAGES: Array<{ id: StageId; name: string; slug: string; hint: string; live: boolean; why: string }> = [
  { id: "dev", name: "Development", slug: "development", hint: "Try changes safely with test data", live: false, why: "Build and test agents without touching real records." },
  { id: "stage", name: "Staging", slug: "staging", hint: "Rehearse with a copy of production", live: false, why: "Check changes against production like data before they go live." },
  { id: "prod", name: "Production", slug: "production", hint: "Live for everyone", live: true, why: "" },
]

const METRICS = ["Workflows", "Agents", "Connectors", "Sources"]

export function TrustSafetyEnvironments() {
  const [sel, setSel] = useState<StageId>("prod")
  const [promo, setPromo] = useState(true)
  const env = STAGES.find((s) => s.id === sel) ?? STAGES[2]
  const liveCount = STAGES.filter((s) => s.live).length
  const missing = STAGES.length - liveCount

  return (
    <>
      <Hero
        art="envs"
        eyebrow="Environments · deployment"
        big={liveCount}
        unit={`of ${STAGES.length} stages live`}
        bars={STAGES.map((s) => s.live)}
        advice="Only Production is running. Add Development and Staging so changes are tested before they reach real records."
        actions={
          <button type="button" className="ts-btn dark sm" onClick={() => setSel("dev")}>
            <Icon name="plus" size={15} width={2} />
            New environment
          </button>
        }
        tiles={[
          { value: liveCount, label: "Online", tone: "good" },
          { value: `${liveCount} of ${STAGES.length}`, label: "Configured" },
          { value: "None yet", label: "Workflows", muted: true },
          { value: "None yet", label: "Agents", muted: true },
        ]}
      />
      <section className="ts-card" style={{ padding: "20px 22px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <div>
            <div className="ts-eyebrow">Deployment pipeline</div>
            <div style={{ fontWeight: 600, marginTop: 4 }}>Promote changes stage by stage</div>
          </div>
          {missing > 0 ? <Pill bg={TONE.warn.bg} fg={TONE.warn.fg} dot={TONE.warn.dot}>{missing} stages not set up</Pill> : null}
        </div>
        <div style={{ display: "flex", alignItems: "center", marginTop: 18, overflowX: "auto", paddingBottom: 4 }}>
          {STAGES.map((s, i) => {
            const tone = s.live ? TONE.ok : TONE.mute
            const lineC = s.live ? "#19C37D" : "#D3D3CC"
            return (
              <Fragment key={s.id}>
                {i > 0 ? (
                  <svg width="64" height="20" viewBox="0 0 64 20" aria-hidden="true" style={{ flex: "0 0 auto" }}>
                    <path d="M4 10 H 60" stroke={lineC} strokeWidth="2" strokeDasharray="5 5" className="ts-flow2" />
                    <path d="M54 5 l6 5 -6 5" stroke={lineC} strokeWidth="2" fill="none" />
                  </svg>
                ) : null}
                <button
                  type="button"
                  className={`ts-wcard${sel === s.id ? " sel" : ""}${s.live ? "" : " ts-ghost"}`}
                  aria-pressed={sel === s.id}
                  onClick={() => setSel(s.id)}
                  style={{ flex: "1 0 180px", textAlign: "left", font: "inherit", color: "inherit" }}
                >
                  <span style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span className={`ts-ico${s.live ? "" : " mute"}`}><Icon name="servers" /></span>
                    <Pill bg={tone.bg} fg={tone.fg} dot={s.live ? "#19C37D" : "#8A8B85"} live={s.live}>{s.live ? "Active" : "Not set up"}</Pill>
                  </span>
                  <span style={{ fontWeight: 600 }}>{s.name}</span>
                  <span style={{ fontSize: 12, color: "#6A6B64" }}>{s.hint}</span>
                </button>
              </Fragment>
            )
          })}
        </div>
      </section>
      <div className="ts-cols">
        <div className="ts-colmain">
          <section className="ts-card" style={{ overflow: "hidden" }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "center", padding: "20px 22px", borderBottom: "1px solid #EFEFEA" }}>
              <span className="ts-ico" style={{ width: 48, height: 48, borderRadius: 14 }}><Icon name="servers" size={22} /></span>
              <div style={{ flex: "1 1 240px" }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <h3 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>{env.name}</h3>
                  {env.live ? <span className="ts-chip" style={{ cursor: "default", minHeight: 24 }}>Default</span> : null}
                </div>
                <div style={{ display: "flex", gap: 14, marginTop: 4, fontSize: 13, color: "#55564F" }}>
                  <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
                    <span className={`ts-dot${env.live ? " ts-live" : ""}`} style={{ background: env.live ? "#19C37D" : "#8A8B85" }} />
                    {env.live ? "Active" : "Not set up"}
                  </span>
                  <span className="ts-mono" style={{ fontSize: 12 }}>{env.slug}</span>
                </div>
              </div>
            </div>
            {env.live ? (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10, padding: "18px 22px" }}>
                  {METRICS.map((m) => (
                    <div key={m} className="ts-tile">
                      <span className="l">{m}</span>
                      <span style={{ fontSize: 15, fontWeight: 500, color: "#6A6B64" }}>Not reported</span>
                    </div>
                  ))}
                </div>
                <div style={{ padding: "0 22px 20px" }}>
                  <div style={{ fontSize: 13, color: "#55564F", marginBottom: 6 }}>API endpoint</div>
                  <div className="ts-mono" style={{ background: "#F7F7F4", border: "1px solid #EFEFEA", borderRadius: 10, padding: "11px 12px", fontSize: 13, color: "#6A6B64" }}>
                    Not reported yet. It appears after the first deploy.
                  </div>
                </div>
              </>
            ) : (
              <div style={{ padding: "32px 22px", display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: 10 }}>
                <div style={{ fontWeight: 600 }}>{env.name} is not set up</div>
                <p style={{ margin: 0, fontSize: 14, color: "#55564F", maxWidth: 420, lineHeight: 1.5 }}>{env.why}</p>
                <button type="button" className="ts-btn green sm">
                  <Icon name="plus" size={15} width={2} />
                  Create {env.name}
                </button>
              </div>
            )}
          </section>
        </div>
        <aside className="ts-colside" aria-label="Promotion rules">
          <section className="ts-card ts-side">
            <div className="ts-sidetitle"><span className="ts-ico sm"><Icon name="up" size={15} /></span>Promotion rules</div>
            <div className="ts-mini">
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 500 }}>Approve before Production</div>
                <div style={{ fontSize: 12, color: "#6A6B64" }}>Uses the approval routing</div>
              </div>
              <Switch on={promo} label="Require approval to promote to Production" onToggle={() => setPromo((v) => !v)} />
            </div>
          </section>
          <Note><strong>Organization wide.</strong> Environment changes apply to everyone in this workspace.</Note>
        </aside>
      </div>
    </>
  )
}
