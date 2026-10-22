import { useCallback, useEffect, useState } from "react"
import { ART } from "../art"
import {
  isPastSla,
  lockNote,
  policyCopy,
  policyLine,
  slaLine,
  titleCase,
  typeLabel,
  whatWillHappen,
  type Approval,
} from "@web/components/approvals/decision-queue/model"
import { useStore } from "../store"
import { Avatar, Empty, ErrorLine, Live, Logo, PageHead } from "../ui"
import { systemBadge, timeAgo } from "../lib/model"

type Priority = "all" | "high" | "medium" | "low"

function approvers(a: Approval): string {
  const roles = a.policy?.approverRoles
  if (roles && roles.length) return roles.map((r) => titleCase(r)).join(", ")
  if (a.policy?.source === "extension_confirm") return "The person who proposed it, or an admin"
  return "Workspace admins and anyone allowed to approve"
}

export function Approvals() {
  const { approvals, history, nav, api, toast, refresh, go, web } = useStore()
  const [priority, setPriority] = useState<Priority>("all")
  const [selected, setSelected] = useState<string | null>(nav.select ?? null)
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (nav.select) setSelected(nav.select)
  }, [nav.select])

  const all = approvals.data
  const rows = all.filter((a) => priority === "all" || a.priority === priority)
  const sel = rows.find((a) => a.id === selected) || rows[0] || null
  const pastSla = all.filter((a) => isPastSla(a)).length
  const approvedN = history.at ? history.data.filter((a) => a.status === "approved").length : null
  const rejectedN = history.at ? history.data.filter((a) => a.status === "rejected").length : null

  const decide = useCallback(
    async (a: Approval, approve: boolean) => {
      if (busy) return
      setBusy(true)
      try {
        if (approve) {
          const result = await api.approve(a.id)
          if (result && result.success === false) {
            toast(String(result.message ?? "Approved, but the action didn't run."), "error")
          } else {
            toast(String(result?.status ?? "") === "pending_approval" ? "Recorded. Another approver is still needed." : `Approved · ${a.title}`)
          }
        } else {
          await api.reject(a.id, reason.trim())
          toast(`Rejected · ${a.title}`)
        }
        setRejecting(false)
        setReason("")
        const idx = rows.findIndex((r) => r.id === a.id)
        setSelected(rows[idx + 1]?.id ?? rows[idx - 1]?.id ?? null)
        await refresh("approvals")
      } catch (err) {
        toast(err instanceof Error ? err.message : "That didn't go through", "error")
        await refresh("approvals")
      } finally {
        setBusy(false)
      }
    },
    [api, busy, reason, refresh, rows, toast],
  )

  // A and R decide the selected request, like the web queue.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      if (!sel || rejecting || e.metaKey || e.ctrlKey || e.altKey) return
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT")) return
      if (e.key === "a" || e.key === "A") void decide(sel, true)
      if (e.key === "r" || e.key === "R") setRejecting(true)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [decide, rejecting, sel])

  const n = all.length
  const lede = !approvals.at
    ? "Loading the decision queue…"
    : n
      ? `Oldest first.${pastSla ? ` ${pastSla} past ${pastSla === 1 ? "its" : "their"} SLA.` : " Every item is within its SLA."}`
      : "No decisions are waiting. New requests appear the moment an agent pauses."
  const policy = sel ? policyCopy(sel) : null
  const sla = sel ? slaLine(sel) : null
  const rowsWhat = sel ? whatWillHappen(sel) : []

  return (
    <div className="page fade">
      <PageHead eyebrow="Governance" title="Approvals" lede="The same decision queue as Trust & Safety. Approve or reject what agents ask to do, with every detail in view.">
        <Live at={approvals.at} />
        <button className="btn" onClick={() => web("/trust-safety?tab=approvals")}>
          Open in Trust &amp; Safety ↗
        </button>
      </PageHead>
      <section className="bigcard" style={{ padding: "22px 24px", display: "flex", gap: 24, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 280, display: "flex", flexDirection: "column", gap: 8 }}>
          <span className="eyebrow">Approvals · decision queue</span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
            <span style={{ fontSize: 44, fontWeight: 600, lineHeight: 1 }}>{approvals.at ? n : "–"}</span>
            <span style={{ fontSize: 16, color: "var(--t2)" }}>waiting on you</span>
          </div>
          <span style={{ fontSize: 14, color: "var(--t2)" }}>{lede}</span>
          <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
            <button className="btn btn-k" onClick={() => go("settings")}>
              Notification rules
            </button>
            <button className="btn btn-l" onClick={() => web("/trust-safety?tab=audit")}>
              View past decisions
            </button>
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 146px)", gap: 8 }}>
          <div className="tile">
            <b>{approvals.at ? n : "–"}</b>
            <span className="sub">Waiting on you</span>
          </div>
          <div className={`tile ${pastSla ? "warn" : ""}`}>
            <b>{approvals.at ? pastSla : "–"}</b>
            <span className={pastSla ? "" : "sub"} style={pastSla ? { fontSize: 12 } : undefined}>
              Past SLA
            </span>
          </div>
          <div className="tile good">
            <b>{approvedN ?? "–"}</b>
            <span style={{ fontSize: 12 }}>Approved</span>
          </div>
          <div className="tile">
            <b>{rejectedN ?? "–"}</b>
            <span className="sub">Rejected</span>
          </div>
        </div>
      </section>
      {approvals.error ? <ErrorLine message={approvals.error} onRetry={() => void refresh("approvals")} /> : null}
      <section className="card" style={{ overflow: "hidden" }}>
        <div className="band" style={{ padding: "14px 20px", display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <span style={{ fontSize: 15, fontWeight: 600 }}>Decision queue</span>
            <span className="sub">Oldest first, across every agent and workflow</span>
          </div>
          <div className="tabs" role="tablist" aria-label="Priority">
            {(["all", "high", "medium", "low"] as Priority[]).map((p) => (
              <button key={p} className={priority === p ? "on" : ""} role="tab" aria-selected={priority === p} onClick={() => setPriority(p)}>
                {p === "all" ? "All" : titleCase(p)}
                {p !== "all" ? <span className="n">{all.filter((a) => a.priority === p).length}</span> : null}
              </button>
            ))}
          </div>
        </div>
        {rows.length === 0 ? (
          approvals.at ? (
            <Empty art={ART.inboxZero} title="All clear" body={n ? "Nothing at this priority." : "No decisions are waiting. New requests appear the moment an agent pauses for a human."} />
          ) : (
            <div className="sub" style={{ padding: 24 }}>
              Loading…
            </div>
          )
        ) : (
          <div className="split" style={{ height: 560 }}>
            <div style={{ width: 360, flex: "none", borderRight: "1px solid var(--bs)", overflow: "auto", padding: 8, display: "flex", flexDirection: "column", gap: 2 }}>
              {rows.map((a) => (
                <button
                  key={a.id}
                  className={`lr ${sel?.id === a.id ? "on" : ""}`}
                  onClick={() => {
                    setSelected(a.id)
                    setRejecting(false)
                  }}
                >
                  <Avatar name={a.requestedBy} />
                  <span style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
                    <span style={{ display: "flex", gap: 8 }}>
                      <span style={{ fontSize: 14, fontWeight: 600, flex: 1, minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{a.title}</span>
                      <span className="sub">{timeAgo(a.requestedAt)}</span>
                    </span>
                    <span style={{ fontSize: 12, color: "var(--t3)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {a.requestedBy} · {policyLine(a)}
                    </span>
                  </span>
                </button>
              ))}
            </div>
            {sel ? (
              <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
                <div className="fade" key={sel.id} style={{ flex: 1, overflow: "auto", padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className={`pill ${sla?.breached ? "st-fail" : "st-wait"}`}>
                      <span className="dot" />
                      {sla ? sla.text : "Waiting on you"}
                    </span>
                    <span style={{ flex: 1 }} />
                    <Logo text={systemBadge(sel.context.integration)} />
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <h2 style={{ margin: 0, fontSize: 22, fontWeight: 600, letterSpacing: "-0.01em" }}>{sel.title}</h2>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--t2)" }}>
                      <Avatar name={sel.requestedBy} size={20} />
                      Requested by {sel.requestedBy} · {typeLabel(sel)}
                    </span>
                    {sel.description && sel.description !== sel.title ? <span style={{ fontSize: 14, color: "var(--t2)" }}>{sel.description}</span> : null}
                  </div>
                  <div style={{ border: "1px solid var(--bd)", borderRadius: 14, overflow: "hidden" }}>
                    <div style={{ padding: "10px 16px", background: "var(--band)" }}>
                      <span className="eyebrow">What happens if you approve</span>
                    </div>
                    {rowsWhat.length === 0 ? (
                      <div className="kv">
                        <span style={{ color: "var(--t3)" }}>Details</span>
                        <span>Not reported for this request</span>
                      </div>
                    ) : (
                      rowsWhat.map((r, i) => (
                        <div key={i} className="kv">
                          <span style={{ color: "var(--t3)" }}>{r.term}</span>
                          {r.href ? (
                            <button className="btn btn-l btn-sm" style={{ justifySelf: "start", padding: 0 }} onClick={() => web(r.href!)}>
                              {r.value} ↗
                            </button>
                          ) : (
                            <span className={`new ${r.mono ? "mono" : ""}`} style={{ overflowWrap: "anywhere" }}>
                              {r.value}
                            </span>
                          )}
                        </div>
                      ))
                    )}
                    {sel.steps.length ? (
                      <div className="kv" style={{ alignItems: "start", paddingTop: 10, paddingBottom: 10 }}>
                        <span style={{ color: "var(--t3)" }}>Steps</span>
                        <span style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                          {sel.steps.map((s, i) => (
                            <span key={i}>
                              {i + 1}. {s.text}
                              {s.access === "write" ? <span className="pill st-wait" style={{ height: 18, marginLeft: 6, fontSize: 11 }}>Writes</span> : null}
                            </span>
                          ))}
                        </span>
                      </div>
                    ) : null}
                  </div>
                  <div style={{ border: "1px solid var(--bd)", borderRadius: 14, overflow: "hidden" }}>
                    <div style={{ padding: "10px 16px", background: "var(--band)" }}>
                      <span className="eyebrow">Why this needs approval</span>
                    </div>
                    <div className="kv">
                      <span style={{ color: "var(--t3)" }}>Policy</span>
                      <span>{policy?.title || policyLine(sel)}</span>
                    </div>
                    <div className="kv">
                      <span style={{ color: "var(--t3)" }}>Who can approve</span>
                      <span>{approvers(sel)}</span>
                    </div>
                    {sel.context.riskLevel ? (
                      <div className="kv">
                        <span style={{ color: "var(--t3)" }}>Risk</span>
                        <span>{titleCase(sel.context.riskLevel)}</span>
                      </div>
                    ) : null}
                  </div>
                  {rejecting ? (
                    <div className="fade" style={{ padding: "14px 16px", borderRadius: 14, border: "1px solid var(--bd)", display: "flex", flexDirection: "column", gap: 8 }}>
                      <label htmlFor="rej" style={{ fontSize: 13, fontWeight: 600 }}>
                        Why are you rejecting this?
                      </label>
                      <textarea id="rej" rows={2} autoFocus className="field" placeholder="The agent sees your reason and can replan" value={reason} onChange={(e) => setReason(e.target.value)} style={{ height: "auto", padding: "8px 10px", resize: "none" }} />
                      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                        <button className="btn btn-q btn-sm" onClick={() => setRejecting(false)}>
                          Cancel
                        </button>
                        <button className="btn btn-dp btn-sm" disabled={busy} onClick={() => void decide(sel, false)}>
                          Reject
                        </button>
                      </div>
                    </div>
                  ) : null}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 24px", borderTop: "1px solid var(--bs)" }}>
                  <span className="sub" style={{ flex: 1 }}>
                    {lockNote(sel)}
                  </span>
                  <button className="btn btn-d" disabled={busy} onClick={() => setRejecting(true)}>
                    Reject <span className="kbd">R</span>
                  </button>
                  <button className="btn btn-k" disabled={busy} onClick={() => void decide(sel, true)}>
                    Approve{" "}
                    <span className="kbd" style={{ background: "transparent", color: "inherit", borderColor: "currentColor", opacity: 0.7 }}>
                      A
                    </span>
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </section>
    </div>
  )
}
