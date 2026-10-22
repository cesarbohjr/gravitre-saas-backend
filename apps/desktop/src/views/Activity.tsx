import { useEffect, useState } from "react"
import { useStore } from "../store"
import { Avatar, ErrorLine, Icon, Logo, PageHead } from "../ui"
import { activityActor, activityStatus, clock, dayLabel, systemBadge } from "../lib/model"
import type { ActivityEvent } from "../lib/api"

function titleOf(e: ActivityEvent): string {
  return e.title?.trim() || (e.event_type || "Activity").replace(/[._]/g, " ").replace(/^./, (c) => c.toUpperCase())
}

function systemsOf(e: ActivityEvent): string {
  const m = e.metadata || {}
  const list = Array.isArray(m.integrations) ? (m.integrations as unknown[]).map(String) : []
  const named = [e.integration, ...list].filter(Boolean) as string[]
  return [...new Set(named.map((s) => s.replace(/[_-]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())))].join(", ")
}

export function Activity() {
  const { activity, nav, refresh, web } = useStore()
  const [open, setOpen] = useState<string | null>(nav.select ?? null)

  useEffect(() => {
    if (nav.select) setOpen(nav.select)
  }, [nav.select])

  const events = activity.data
  const dr = events.find((e) => e.id === open) || null
  let lastGroup = ""

  return (
    <div className="page fade">
      <PageHead eyebrow="Audit · what ran and what changed" title="Activity" lede="Every run, change and decision, grouped by day. Open any item for who, what, which systems and the result.">
        <button className="btn" onClick={() => web("/trust-safety?tab=audit")}>
          Full audit trail ↗
        </button>
      </PageHead>
      {activity.error && !activity.at ? <ErrorLine message={activity.error} onRetry={() => void refresh("activity")} /> : null}
      <div className="card split" style={{ height: 620, overflow: "hidden" }}>
        <div style={{ flex: 1, minWidth: 0, overflow: "auto", padding: "8px 14px 14px" }}>
          {events.length === 0 ? (
            <div className="sub" style={{ padding: 16 }}>
              {activity.at ? "Nothing has run yet. Runs, changes and decisions show up here as they happen." : "Loading…"}
            </div>
          ) : null}
          {events.map((e) => {
            const group = dayLabel(e.created_at)
            const header = group !== lastGroup
            lastGroup = group
            const st = activityStatus(e)
            const who = activityActor(e)
            return (
              <div key={e.id}>
                {header ? (
                  <div className="eyebrow" style={{ padding: "16px 8px 6px" }}>
                    {group}
                  </div>
                ) : null}
                <button className={`lr ${open === e.id ? "on" : ""}`} onClick={() => setOpen(e.id)} style={{ alignItems: "center", minHeight: 52, padding: "0 12px" }}>
                  <span className="mono" style={{ fontSize: 12, color: "var(--t3)", width: 62, flex: "none" }}>
                    {clock(e.created_at)}
                  </span>
                  <Avatar name={who} size={24} />
                  <span style={{ flex: 1, minWidth: 0, fontSize: 14, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{titleOf(e)}</span>
                  <Logo text={systemBadge(e.integration)} />
                  <span className={`pill ${st.cls}`}>{st.label}</span>
                </button>
              </div>
            )
          })}
        </div>
        {dr ? (
          <aside className="fade" role="dialog" aria-label="Activity details" style={{ width: 380, flex: "none", borderLeft: "1px solid var(--bs)", display: "flex", flexDirection: "column", background: "var(--s1)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "14px 12px 14px 20px", background: "var(--band)", borderBottom: "1px solid var(--bs)" }}>
              <span className={`pill ${activityStatus(dr).cls}`}>{activityStatus(dr).label}</span>
              <span style={{ flex: 1 }} />
              <button className="ib" aria-label="Close details" onClick={() => setOpen(null)}>
                <Icon name="x" />
              </button>
            </div>
            <div style={{ flex: 1, overflow: "auto", padding: "18px 20px", display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ fontSize: 18, fontWeight: 600 }}>{titleOf(dr)}</span>
                <span className="sub">
                  {dayLabel(dr.created_at)} · {clock(dr.created_at)}
                </span>
              </div>
              <div style={{ border: "1px solid var(--bd)", borderRadius: 12, overflow: "hidden" }}>
                <div className="kv" style={{ gridTemplateColumns: "90px 1fr", borderTop: 0 }}>
                  <span style={{ color: "var(--t3)" }}>Who</span>
                  <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <Avatar name={activityActor(dr)} size={20} />
                    {activityActor(dr)}
                  </span>
                </div>
                {systemsOf(dr) ? (
                  <div className="kv" style={{ gridTemplateColumns: "90px 1fr" }}>
                    <span style={{ color: "var(--t3)" }}>Systems</span>
                    <span>{systemsOf(dr)}</span>
                  </div>
                ) : null}
                {dr.entity_type ? (
                  <div className="kv" style={{ gridTemplateColumns: "90px 1fr" }}>
                    <span style={{ color: "var(--t3)" }}>About</span>
                    <span>{dr.entity_type.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase())}</span>
                  </div>
                ) : null}
              </div>
              {dr.body ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <span className="eyebrow">Result</span>
                  <span style={{ display: "flex", gap: 8, fontSize: 14, whiteSpace: "pre-wrap" }}>{dr.body}</span>
                </div>
              ) : null}
            </div>
            <div style={{ display: "flex", gap: 8, padding: "12px 20px", borderTop: "1px solid var(--bs)" }}>
              <button className="btn btn-sm" style={{ flex: 1 }} onClick={() => web("/trust-safety?tab=audit")}>
                Audit trail ↗
              </button>
              <button className="btn btn-sm" style={{ flex: 1 }} onClick={() => web(dr.url || "/activity")}>
                Open on web ↗
              </button>
            </div>
          </aside>
        ) : null}
      </div>
    </div>
  )
}
