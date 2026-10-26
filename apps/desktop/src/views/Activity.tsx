import { useEffect, useMemo, useState } from "react"
import { ART } from "../art"
import { useStore } from "../store"
import { AgentAvatar, Empty, ErrorLine, Icon, Logo } from "../ui"
import { activityActor, activityStatus, clock, dayLabel, systemBadge } from "../lib/model"
import { identityOf } from "../lib/identity"
import type { ActivityEvent } from "../lib/api"

const pretty = (s: string) => s.replace(/[_-]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())

function titleOf(e: ActivityEvent): string {
  return e.title?.trim() || pretty(e.event_type || "Activity").replace(/\b\w/g, (c, i) => (i ? c.toLowerCase() : c))
}

function systemsOf(e: ActivityEvent): string[] {
  const m = e.metadata || {}
  const list = Array.isArray(m.integrations) ? (m.integrations as unknown[]).map(String) : []
  return [...new Set([e.integration, ...list].filter(Boolean) as string[])]
}

/** Result lines the event reported: a list when it sent one, otherwise its body. */
function resultLines(e: ActivityEvent): string[] {
  const m = e.metadata || {}
  const list = Array.isArray(m.results) ? m.results : Array.isArray(m.changes) ? m.changes : null
  if (list) return list.map((x) => (typeof x === "string" ? x : JSON.stringify(x))).filter(Boolean)
  return e.body ? e.body.split(/\n+/).map((l) => l.replace(/^[-•]\s*/, "").trim()).filter(Boolean) : []
}

function approvalLine(e: ActivityEvent): string | null {
  const m = e.metadata || {}
  const v = m.approval_status ?? m.approval ?? null
  if (typeof v === "string" && v) return pretty(v)
  if (m.requires_approval === false) return "Not needed"
  return null
}

export function Activity() {
  const { activity, nav, refresh, web, agents } = useStore()
  const [open, setOpen] = useState<string | null>(nav.select ?? null)
  const [agent, setAgent] = useState("")
  const [system, setSystem] = useState("")

  useEffect(() => {
    if (nav.select) setOpen(nav.select)
  }, [nav.select])

  const events = activity.data
  const actors = useMemo(() => [...new Set(events.map(activityActor))].sort(), [events])
  const systems = useMemo(() => [...new Set(events.flatMap(systemsOf))].sort(), [events])
  const shown = events.filter((e) => (!agent || activityActor(e) === agent) && (!system || systemsOf(e).includes(system)))
  const dr = events.find((e) => e.id === open) || null
  let lastGroup = ""

  return (
    <div className="body fade" style={{ minHeight: 0 }}>
      <section className="dpane" aria-label="Activity">
        <div className="lhead" style={{ padding: "18px 24px 8px" }}>
          <h1>Activity</h1>
          <span style={{ flex: 1 }} />
          <select className="select select-sm" style={{ width: "auto" }} aria-label="Agent" value={agent} onChange={(e) => setAgent(e.target.value)}>
            <option value="">All agents</option>
            {actors.map((a) => (
              <option key={a}>{a}</option>
            ))}
          </select>
          <select className="select select-sm" style={{ width: "auto" }} aria-label="System" value={system} onChange={(e) => setSystem(e.target.value)}>
            <option value="">All systems</option>
            {systems.map((s) => (
              <option key={s} value={s}>
                {pretty(s)}
              </option>
            ))}
          </select>
        </div>
        <div className="scroll" style={{ flex: 1, padding: "0 16px 16px" }}>
          {activity.error && !activity.at ? <ErrorLine message={activity.error} onRetry={() => void refresh("activity")} /> : null}
          {shown.length === 0 ? (
            activity.at ? (
              events.length ? (
                <div className="sub" style={{ padding: 12 }}>
                  Nothing matches these filters.
                </div>
              ) : (
                <Empty art={ART.reports} title="Nothing has run yet" body="Runs, changes and decisions show up here as they happen." />
              )
            ) : (
              <div className="sub" style={{ padding: 12 }}>
                Loading…
              </div>
            )
          ) : null}
          {shown.map((e) => {
            const group = dayLabel(e.created_at)
            const header = group !== lastGroup
            lastGroup = group
            const st = activityStatus(e)
            return (
              <div key={e.id}>
                {header ? (
                  <div style={{ padding: "14px 8px 6px", fontSize: 12, fontWeight: 600, color: "var(--t2)" }}>{group}</div>
                ) : null}
                <button className={`lr ${open === e.id ? "on" : ""}`} aria-current={open === e.id ? "true" : undefined} onClick={() => setOpen(e.id)} style={{ alignItems: "center", minHeight: 42, padding: "0 10px" }}>
                  <span className="mono sub" style={{ width: 64, flex: "none", whiteSpace: "nowrap" }}>
                    {clock(e.created_at)}
                  </span>
                  <AgentAvatar id={identityOf(agents, activityActor(e))} size={20} />
                  <span className="ell" style={{ flex: 1, minWidth: 0, fontSize: 13 }}>
                    {titleOf(e)}
                  </span>
                  <Logo text={systemBadge(e.integration)} />
                  <span className={`pill ${st.cls}`}>{st.label}</span>
                </button>
              </div>
            )
          })}
        </div>
      </section>
      {dr ? (
        <aside className="fade" role="dialog" aria-label="Activity details" style={{ width: 312, flex: "none", borderLeft: "1px solid var(--bd)", display: "flex", flexDirection: "column", background: "var(--s1)", minHeight: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 12px 12px 16px", borderBottom: "1px solid var(--bs)" }}>
            <span className={`pill ${activityStatus(dr).cls}`}>
              <span className="dot" />
              {activityStatus(dr).label}
            </span>
            <span style={{ flex: 1 }} />
            <button className="ib" aria-label="Close details" onClick={() => setOpen(null)}>
              <Icon name="x" />
            </button>
          </div>
          <div className="scroll" style={{ flex: 1, padding: "16px", display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <span style={{ fontSize: 16, fontWeight: 600 }}>{titleOf(dr)}</span>
              <span className="sub">
                {dayLabel(dr.created_at)} {clock(dr.created_at)}
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <div className="kv" style={{ gridTemplateColumns: "80px 1fr", borderTop: 0, padding: 0 }}>
                <span>Who</span>
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <AgentAvatar id={identityOf(agents, activityActor(dr))} size={18} />
                  {activityActor(dr)}
                </span>
              </div>
              {dr.entity_type ? (
                <div className="kv" style={{ gridTemplateColumns: "80px 1fr", padding: 0 }}>
                  <span>What</span>
                  <span>{pretty(dr.entity_type)}</span>
                </div>
              ) : null}
              {systemsOf(dr).length ? (
                <div className="kv" style={{ gridTemplateColumns: "80px 1fr", padding: 0 }}>
                  <span>Systems</span>
                  <span style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {systemsOf(dr).map((s) => (
                      <span key={s} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                        <Logo text={systemBadge(s)} />
                        {pretty(s)}
                      </span>
                    ))}
                  </span>
                </div>
              ) : null}
              {approvalLine(dr) ? (
                <div className="kv" style={{ gridTemplateColumns: "80px 1fr", padding: 0 }}>
                  <span>Approval</span>
                  <span>{approvalLine(dr)}</span>
                </div>
              ) : null}
            </div>
            {resultLines(dr).length ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>Result</span>
                <div className="card" style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 6, boxShadow: "none" }}>
                  {resultLines(dr).map((l, i) => (
                    <span key={i} style={{ display: "flex", gap: 8, fontSize: 13 }}>
                      <Icon name={activityStatus(dr).cls === "st-fail" ? "alert" : "check"} size={13} style={{ color: activityStatus(dr).cls === "st-fail" ? "var(--dg)" : "var(--ok)", marginTop: 3, flex: "none" }} />
                      {l}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
          <div style={{ display: "flex", gap: 8, padding: "12px 16px", borderTop: "1px solid var(--bs)" }}>
            <button className="btn btn-sm" style={{ flex: 1 }} onClick={() => web("/trust-safety?tab=audit")}>
              View audit entry ↗
            </button>
            <button className="btn btn-sm" style={{ flex: 1 }} onClick={() => web(dr.url || "/activity")}>
              Open results on web ↗
            </button>
          </div>
        </aside>
      ) : null}
    </div>
  )
}
