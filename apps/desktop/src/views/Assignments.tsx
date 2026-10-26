import { useEffect, useState } from "react"
import { ART } from "../art"
import { useStore } from "../store"
import { AgentAvatar, Empty, ErrorLine, Icon, Logo, StatusPill, StepDot } from "../ui"
import { clock, dayLabel, progressLine, type Assignment, type Status } from "../lib/model"
import { identityOf } from "../lib/identity"

type Filter = "all" | "running" | "waiting" | "done" | "failed"

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "running", label: "Running" },
  { key: "waiting", label: "Waiting" },
  { key: "done", label: "Done" },
  { key: "failed", label: "Failed" },
]

function matches(a: Assignment, f: Filter): boolean {
  if (f === "all") return true
  if (f === "running") return a.status === "running" || a.status === "queued" || a.status === "paused"
  return a.status === (f as Status)
}

function rowLine(a: Assignment): string {
  if (a.status === "done" || a.status === "failed") return a.outcome || ""
  return progressLine(a)
}

function when(iso: string): string {
  const d = dayLabel(iso)
  return d === "Today" ? clock(iso) : d
}

export function Assignments() {
  const { assignments, nav, api, toast, refresh, web, agents, canApprove } = useStore()
  const [filter, setFilter] = useState<Filter>("all")
  const [selected, setSelected] = useState<string | null>(nav.select ?? null)
  const [busy, setBusy] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState("")

  useEffect(() => {
    if (nav.select) {
      setSelected(nav.select)
      setFilter("all")
    }
  }, [nav.select])

  const all = assignments.data
  const rows = all.filter((a) => matches(a, filter))
  const sel = rows.find((a) => a.id === selected) || rows[0] || null
  const doneN = sel ? sel.steps.filter((s) => s.state === "done").length : 0

  const act = async (fn: () => Promise<void>, ok: string) => {
    if (busy) return
    setBusy(true)
    try {
      await fn()
      toast(ok)
      setRejecting(false)
      setReason("")
      await refresh("assignments")
    } catch (err) {
      toast(err instanceof Error ? err.message : "That didn't work", "error")
    } finally {
      setBusy(false)
    }
  }

  const k = sel ? (sel.status === "done" ? "done" : sel.status === "failed" ? "fail" : "pending") : "pending"
  const who = sel ? identityOf(agents, sel.agent, sel.agentId) : null

  return (
    <div className="body fade" style={{ minHeight: 0 }}>
      <section className="lpane" aria-label="Assignments" style={{ width: 296 }}>
        <div className="lhead">
          <h1>Assignments</h1>
          <button className="mlink" onClick={() => web("/assignments/new")}>
            New on web ↗
          </button>
        </div>
        <div style={{ padding: "0 12px 8px" }}>
          <div className="seg" role="tablist" aria-label="Status" style={{ overflowX: "auto" }}>
            {FILTERS.map((f) => {
              const n = all.filter((a) => matches(a, f.key)).length
              return (
                <button key={f.key} className={filter === f.key ? "on" : ""} role="tab" aria-selected={filter === f.key} onClick={() => setFilter(f.key)} style={{ padding: "0 7px" }}>
                  {f.label}
                  {n ? <span style={{ marginLeft: 4 }}>{n}</span> : null}
                </button>
              )
            })}
          </div>
        </div>
        <div className="scroll" style={{ flex: 1, padding: "0 8px 8px", display: "flex", flexDirection: "column", gap: 2 }}>
          {assignments.error && !assignments.at ? <ErrorLine message={assignments.error} onRetry={() => void refresh("assignments")} /> : null}
          {rows.length === 0 ? (
            <div className="sub" style={{ padding: 12 }}>
              {assignments.at ? (filter === "all" ? "No assignments yet. Hand an objective to an agent on the web or from Ask." : "Nothing here right now.") : "Loading…"}
            </div>
          ) : null}
          {rows.map((a) => (
            <button
              key={a.id}
              className={`lr ${sel?.id === a.id ? "on" : ""}`}
              aria-current={sel?.id === a.id ? "true" : undefined}
              onClick={() => {
                setSelected(a.id)
                setRejecting(false)
              }}
            >
              <AgentAvatar id={identityOf(agents, a.agent, a.agentId)} size={26} />
              <span style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                  <span className="ell" style={{ fontSize: 13, fontWeight: 600, flex: 1 }}>
                    {a.title}
                  </span>
                  <span className="sub">{when(a.createdAt)}</span>
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                  <StatusPill status={a.status} />
                  <span className="sub ell">{rowLine(a)}</span>
                </span>
              </span>
            </button>
          ))}
        </div>
      </section>
      {sel && who ? (
        <section className="dpane" aria-label="Assignment detail">
          <div className="scroll fade" key={sel.id} style={{ flex: 1 }}>
            <div className="dhead">
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <StatusPill status={sel.status} />
                <span className="sub" style={{ flex: 1 }}>
                  Started {dayLabel(sel.createdAt) === "Today" ? clock(sel.createdAt) : `${dayLabel(sel.createdAt)} ${clock(sel.createdAt)}`}
                </span>
                {sel.status === "running" ? (
                  <button className="btn btn-sm" disabled={busy} onClick={() => void act(() => api.pauseJob(sel.id), "Pause requested")}>
                    <Icon name="pause" size={13} /> Pause
                  </button>
                ) : null}
                <button className="btn btn-sm" onClick={() => web(`/assignments/${encodeURIComponent(sel.id)}`)}>
                  Open on web ↗
                </button>
              </div>
              <h2>{sel.title}</h2>
              <span style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <span className="chip">
                  <AgentAvatar id={who} size={16} />
                  {sel.agent} · {who.dept.label}
                </span>
              </span>
            </div>
            <div style={{ padding: "16px 24px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>Objective</span>
                <span style={{ fontSize: 14, lineHeight: 1.55, color: "var(--t2)" }}>{sel.objective}</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex" }}>
                  <span style={{ fontSize: 13, fontWeight: 600, flex: 1 }}>Plan</span>
                  <span className="sub">
                    {doneN} of {sel.steps.length} done
                  </span>
                </div>
                <div className="card" style={{ overflow: "hidden" }}>
                  {sel.steps.map((st, i) => (
                    <div key={i} style={{ borderTop: i ? "1px solid var(--bs)" : 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 12, minHeight: 50, padding: "6px 14px" }}>
                        <StepDot state={st.state} />
                        <span style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
                          <span style={{ fontSize: 13, fontWeight: 500 }}>{st.title}</span>
                          <span className="sub">{st.detail}</span>
                        </span>
                        <Logo text={st.system} />
                      </div>
                      {st.state === "waiting" && sel.status === "waiting" ? (
                        <div style={{ margin: "0 14px 12px 48px", border: rejecting ? "1px solid var(--bd)" : 0, borderRadius: 10, overflow: "hidden" }}>
                          {rejecting ? (
                            <div className="fade" style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 8 }}>
                              <label htmlFor="arej" style={{ fontSize: 13, fontWeight: 600 }}>
                                Why are you rejecting this?
                              </label>
                              <textarea
                                id="arej"
                                rows={2}
                                autoFocus
                                className="field"
                                placeholder={`${sel.agent} sees your reason`}
                                value={reason}
                                onChange={(e) => setReason(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Escape") setRejecting(false)
                                }}
                                style={{ height: "auto", padding: "8px 10px", resize: "none" }}
                              />
                            </div>
                          ) : null}
                          <div style={{ padding: rejecting ? "8px 12px" : 0, display: "flex", gap: 8, alignItems: "center", borderTop: rejecting ? "1px solid var(--bs)" : 0 }}>
                            <span className="sub" style={{ flex: 1 }}>
                              {canApprove ? "" : "Your role can't approve changes. An admin can."}
                            </span>
                            {rejecting ? (
                              <>
                                <button className="btn btn-q btn-sm" onClick={() => setRejecting(false)}>
                                  Cancel
                                </button>
                                <button className="btn btn-dp btn-sm" disabled={busy} onClick={() => void act(() => api.rejectJob(sel.id, reason.trim()), `Rejected: ${sel.title}`)}>
                                  Reject
                                </button>
                              </>
                            ) : (
                              <>
                                <button className="btn btn-d btn-sm" disabled={!canApprove} onClick={() => setRejecting(true)}>
                                  Reject
                                </button>
                                <button className="btn btn-p btn-sm" disabled={busy || !canApprove} onClick={() => void act(() => api.approveJob(sel.id), `Approved: ${sel.title}`)}>
                                  Approve
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>Outcome</span>
                <div
                  style={{
                    border: `1px ${k === "pending" ? "dashed" : "solid"} var(--bd)`,
                    borderRadius: 12,
                    padding: "12px 14px",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 10,
                    background: k === "done" ? "var(--brs)" : k === "fail" ? "var(--dgs)" : "transparent",
                  }}
                >
                  <Icon name={k === "done" ? "checkc" : k === "fail" ? "alert" : "clock"} style={{ color: k === "done" ? "var(--ok)" : k === "fail" ? "var(--dg)" : "var(--t3)", marginTop: 2 }} />
                  <span style={{ fontSize: 13, flex: 1, whiteSpace: "pre-wrap", color: "var(--t2)" }}>
                    {sel.outcome || "Not finished. The result shows here when the run ends."}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>
      ) : (
        <section className="dpane">
          {assignments.at ? <Empty art={ART.workflows} title="Nothing selected" body="Pick an assignment to see its plan and outcome." /> : null}
        </section>
      )}
    </div>
  )
}
