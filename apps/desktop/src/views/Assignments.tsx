import { useEffect, useState } from "react"
import { ART } from "../art"
import { useStore } from "../store"
import { Avatar, Empty, ErrorLine, Icon, Logo, PageHead, StatusPill, StepDot } from "../ui"
import { timeAgo, type Assignment, type Status } from "../lib/model"

const FILTERS: { key: "all" | Status; label: string; color: string }[] = [
  { key: "all", label: "All", color: "var(--t3)" },
  { key: "running", label: "Running", color: "var(--sig)" },
  { key: "waiting", label: "Waiting", color: "var(--ap)" },
  { key: "done", label: "Done", color: "var(--ok)" },
  { key: "failed", label: "Failed", color: "var(--dg)" },
]

function rowLine(a: Assignment): string {
  if (a.status === "done" || a.status === "failed") return a.outcome || ""
  if (a.status === "waiting") return a.approvalPrompt || "Waiting on your approval"
  return a.steps.find((s) => s.state !== "done")?.title || a.objective
}

export function Assignments() {
  const { assignments, nav, api, toast, refresh, web } = useStore()
  const [filter, setFilter] = useState<"all" | Status>("all")
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
  const rows = all.filter((a) => filter === "all" || a.status === filter)
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

  return (
    <div className="page fade">
      <PageHead eyebrow="Outcomes · plans · approval gates" title="Assignments" lede="Objectives handed to agents. Follow each run step by step, approve gates, and see the outcome.">
        <button className="btn" onClick={() => web("/assignments/new")}>
          New assignment on web ↗
        </button>
      </PageHead>
      {assignments.error && !assignments.at ? <ErrorLine message={assignments.error} onRetry={() => void refresh("assignments")} /> : null}
      <div className="card" style={{ display: "grid", gridTemplateColumns: "repeat(5, minmax(0, 1fr))", overflow: "hidden" }}>
        {FILTERS.map((f) => {
          const on = filter === f.key
          const n = f.key === "all" ? all.length : all.filter((a) => a.status === f.key).length
          return (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              aria-pressed={on}
              style={{ display: "flex", alignItems: "baseline", gap: 10, padding: "18px 20px", border: 0, borderRight: "1px solid var(--bs)", background: on ? "var(--s1)" : "var(--band)", cursor: "pointer", textAlign: "left", boxShadow: on ? "inset 0 -2px 0 var(--ink)" : "none" }}
            >
              <span style={{ fontSize: 26, fontWeight: 600 }}>{assignments.at ? n : "–"}</span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 14, color: "var(--t2)" }}>
                <span className="dot" style={{ background: f.color, width: 7, height: 7 }} />
                {f.label}
              </span>
            </button>
          )
        })}
      </div>
      <div className="card split" style={{ height: 620, overflow: "hidden" }}>
        <div style={{ width: 360, flex: "none", borderRight: "1px solid var(--bs)", overflow: "auto", padding: 8, display: "flex", flexDirection: "column", gap: 2 }}>
          {rows.length === 0 ? (
            <div className="sub" style={{ padding: 14 }}>
              {assignments.at ? (filter === "all" ? "No assignments yet. Hand an objective to an agent on the web or from Ask." : "Nothing here right now.") : "Loading…"}
            </div>
          ) : null}
          {rows.map((a) => (
            <button
              key={a.id}
              className={`lr ${sel?.id === a.id ? "on" : ""}`}
              onClick={() => {
                setSelected(a.id)
                setRejecting(false)
              }}
            >
              <Avatar name={a.agent} size={26} />
              <span style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 5 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 14, fontWeight: 600, flex: 1, minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{a.title}</span>
                  <span className="sub">{timeAgo(a.createdAt)}</span>
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                  <StatusPill status={a.status} />
                  <span style={{ fontSize: 12, color: "var(--t3)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{rowLine(a)}</span>
                </span>
              </span>
            </button>
          ))}
        </div>
        <div style={{ flex: 1, minWidth: 0, overflow: "auto" }}>
          {sel ? (
            <div className="fade" key={sel.id} style={{ padding: "22px 26px", display: "flex", flexDirection: "column", gap: 18 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <StatusPill status={sel.status} />
                <span className="sub" style={{ flex: 1 }}>
                  Started {timeAgo(sel.createdAt)} ago
                </span>
                {sel.status === "running" ? (
                  <button className="btn btn-sm" disabled={busy} onClick={() => void act(() => api.pauseJob(sel.id), "Pause requested")}>
                    Pause
                  </button>
                ) : null}
                <button className="btn btn-sm" onClick={() => web(`/assignments/${encodeURIComponent(sel.id)}`)}>
                  Open on web ↗
                </button>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <h2 style={{ margin: 0, fontSize: 24, fontWeight: 600, letterSpacing: "-0.01em" }}>{sel.title}</h2>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--t2)" }}>
                  <Avatar name={sel.agent} size={22} />
                  Owned by {sel.agent}
                </span>
              </div>
              <div style={{ padding: "14px 16px", borderRadius: 12, background: "var(--s2)", display: "flex", flexDirection: "column", gap: 4 }}>
                <span className="eyebrow">Objective</span>
                <span style={{ fontSize: 14, lineHeight: 1.55 }}>{sel.objective}</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex" }}>
                  <span className="eyebrow" style={{ flex: 1 }}>
                    Steps
                  </span>
                  <span className="mono sub">
                    {doneN} of {sel.steps.length} done
                  </span>
                </div>
                <div style={{ border: "1px solid var(--bd)", borderRadius: 14, overflow: "hidden" }}>
                  {sel.steps.map((st, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, minHeight: 52, padding: "0 16px", borderBottom: i === sel.steps.length - 1 ? 0 : "1px solid var(--bs)" }}>
                      <StepDot state={st.state} />
                      <span style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
                        <span style={{ fontSize: 14, fontWeight: 500 }}>{st.title}</span>
                        <span className="sub">{st.detail}</span>
                      </span>
                      <Logo text={st.system} />
                    </div>
                  ))}
                </div>
              </div>
              {sel.status === "waiting" ? (
                <div style={{ border: "1px solid var(--ap)", borderRadius: 14, overflow: "hidden" }}>
                  <div style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: 8, background: "var(--aps)" }}>
                    <span className="eyebrow" style={{ color: "var(--apk)", flex: 1 }}>
                      Approval gate · {sel.agent} is waiting on you
                    </span>
                  </div>
                  <div className="kv" style={{ borderTop: 0 }}>
                    <span style={{ color: "var(--t3)" }}>Asks</span>
                    <span>{sel.approvalPrompt || "Approve the result so the work can continue."}</span>
                  </div>
                  {rejecting ? (
                    <div className="fade" style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 8, borderTop: "1px solid var(--bs)" }}>
                      <label htmlFor="arej" style={{ fontSize: 13, fontWeight: 600 }}>
                        Why are you rejecting this?
                      </label>
                      <textarea id="arej" rows={2} className="field" placeholder="The agent sees your reason" value={reason} onChange={(e) => setReason(e.target.value)} style={{ height: "auto", padding: "8px 10px", resize: "none" }} />
                    </div>
                  ) : null}
                  <div style={{ padding: "10px 16px", display: "flex", gap: 8, justifyContent: "flex-end", borderTop: "1px solid var(--bs)" }}>
                    {rejecting ? (
                      <>
                        <button className="btn btn-q btn-sm" onClick={() => setRejecting(false)}>
                          Cancel
                        </button>
                        <button className="btn btn-dp btn-sm" disabled={busy} onClick={() => void act(() => api.rejectJob(sel.id, reason.trim()), "Rejected")}>
                          Reject
                        </button>
                      </>
                    ) : (
                      <>
                        <button className="btn btn-d btn-sm" onClick={() => setRejecting(true)}>
                          Reject
                        </button>
                        <button className="btn btn-k btn-sm" disabled={busy} onClick={() => void act(() => api.approveJob(sel.id), "Approved")}>
                          Approve
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ) : null}
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <span className="eyebrow">Outcome</span>
                <div
                  style={{
                    border: `1px ${k === "pending" ? "dashed" : "solid"} var(--bx)`,
                    borderRadius: 14,
                    padding: "14px 16px",
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    background: k === "done" ? "var(--sa)" : k === "fail" ? "var(--dgs)" : "transparent",
                  }}
                >
                  <Icon name={k === "done" ? "checkc" : k === "fail" ? "alert" : "clock"} style={{ color: k === "done" ? "var(--ok)" : k === "fail" ? "var(--dg)" : "var(--t3)" }} />
                  <span style={{ fontSize: 14, flex: 1, whiteSpace: "pre-wrap" }}>{sel.outcome || "The outcome shows here when the run finishes."}</span>
                </div>
              </div>
            </div>
          ) : assignments.at ? (
            <Empty art={ART.workflows} title="Nothing selected" body="Pick an assignment to see its steps and outcome." />
          ) : null}
        </div>
      </div>
    </div>
  )
}
