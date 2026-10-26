import { useCallback, useEffect, useMemo, useState } from "react"
import { ART } from "../art"
import { lockNote, policyLine, slaLine, titleCase, whatWillHappen, type Approval, type DetailRow } from "@web/components/approvals/decision-queue/model"
import { useStore } from "../store"
import { AgentAvatar, Empty, ErrorLine, Logo } from "../ui"
import { age, systemBadge } from "../lib/model"
import { identityOf } from "../lib/identity"

type Priority = "all" | "high" | "medium" | "low"

/** Rows that describe the request rather than a value it writes. */
const META_TERMS = new Set(["Action", "App", "Tool", "Workflow", "Environment", "Approvals needed", "Proposed on", "Impact", "Run"])

function approvers(a: Approval, canApprove: boolean): string {
  const roles = a.policy?.approverRoles
  const who = roles && roles.length ? roles.map((r) => `${titleCase(r)}s`).join(", ") : a.policy?.source === "extension_confirm" ? "The person who proposed it, or Admins" : "Admins"
  return canApprove ? `${who} · you` : who
}

function oldestFirst(a: Approval, b: Approval) {
  return new Date(a.requestedAt || 0).getTime() - new Date(b.requestedAt || 0).getTime()
}

export function Approvals() {
  const { approvals, nav, api, toast, refresh, go, web, agents, approveWithUndo, canApprove } = useStore()
  const [priority, setPriority] = useState<Priority>("all")
  const [selected, setSelected] = useState<string | null>(nav.select ?? null)
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [convTitle, setConvTitle] = useState<Record<string, string>>({})

  useEffect(() => {
    if (nav.select) setSelected(nav.select)
  }, [nav.select])

  const all = useMemo(() => [...approvals.data].sort(oldestFirst), [approvals.data])
  const rows = all.filter((a) => priority === "all" || a.priority === priority)
  const sel = rows.find((a) => a.id === selected) || rows[0] || null

  // The conversation an approval came from, by title.
  const convId = sel?.context.conversationId || null
  useEffect(() => {
    if (!convId || convTitle[convId]) return
    api
      .conversations()
      .then((list) => setConvTitle((m) => ({ ...m, ...Object.fromEntries(list.map((c) => [c.id, c.title])) })))
      .catch(() => {})
  }, [api, convId, convTitle])

  const move = useCallback(
    (by: number) => {
      if (!rows.length) return
      const i = Math.max(0, rows.findIndex((a) => a.id === sel?.id))
      const next = rows[Math.min(rows.length - 1, Math.max(0, i + by))]
      setSelected(next.id)
      setRejecting(false)
    },
    [rows, sel?.id],
  )

  const approve = useCallback(
    (a: Approval) => {
      if (!canApprove) return
      move(1)
      if (rows.length === 1 || rows[rows.length - 1].id === a.id) move(-1)
      approveWithUndo(a)
    },
    [approveWithUndo, canApprove, move, rows],
  )

  const reject = useCallback(
    async (a: Approval) => {
      if (busy) return
      setBusy(true)
      try {
        await api.reject(a.id, reason.trim())
        toast(`Rejected: ${a.title}`)
        setRejecting(false)
        setReason("")
        move(1)
        await refresh("approvals")
      } catch (err) {
        toast(err instanceof Error ? err.message : "That didn't go through", "error")
        await refresh("approvals")
      } finally {
        setBusy(false)
      }
    },
    [api, busy, move, reason, refresh, toast],
  )

  // J and K move, A approves, R rejects, E expands the change table: like the web queue.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      if (rejecting || e.metaKey || e.ctrlKey || e.altKey) return
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT")) return
      const k = e.key.toLowerCase()
      if (k === "j") move(1)
      else if (k === "k") move(-1)
      else if (k === "e") setExpanded((x) => !x)
      else if (!sel) return
      else if (k === "a") approve(sel)
      else if (k === "r" && canApprove) setRejecting(true)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [approve, canApprove, move, rejecting, sel])

  const detail: DetailRow[] = sel ? whatWillHappen(sel) : []
  const fields = detail.filter((r) => !META_TERMS.has(r.term))
  const meta = detail.filter((r) => META_TERMS.has(r.term) && r.term !== "Tool")
  const sla = sel ? slaLine(sel) : null
  const who = sel ? identityOf(agents, sel.requestedBy) : null
  const shownFields = expanded ? fields : fields.slice(0, 6)
  const subject = sel ? [sel.context.integration ? titleCase(sel.context.integration) : null, sel.context.label || sel.context.entity || null].filter(Boolean).join(" · ") : ""
  const convName = convId ? convTitle[convId] || "Open the conversation" : null

  return (
    <div className="body fade" style={{ minHeight: 0 }}>
      <section className="lpane" aria-label="Waiting for approval" style={{ width: 296 }}>
        <div className="lhead">
          <h1>Approvals</h1>
          <span className="sub">Oldest first</span>
        </div>
        <div style={{ padding: "0 12px 8px" }}>
          <div className="seg" role="tablist" aria-label="Priority">
            {(["all", "high", "medium", "low"] as Priority[]).map((p) => (
              <button key={p} className={priority === p ? "on" : ""} role="tab" aria-selected={priority === p} onClick={() => setPriority(p)}>
                {p === "all" ? `All ${all.length || ""}`.trim() : titleCase(p)}
              </button>
            ))}
          </div>
        </div>
        <div className="scroll" style={{ flex: 1, padding: "0 8px 8px", display: "flex", flexDirection: "column", gap: 2 }}>
          {approvals.error && !approvals.at ? <ErrorLine message={approvals.error} onRetry={() => void refresh("approvals")} /> : null}
          {rows.length === 0 ? <div className="sub" style={{ padding: 12 }}>{approvals.at ? (all.length ? "Nothing at this priority." : "Nothing is waiting on you.") : "Loading…"}</div> : null}
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
              <AgentAvatar id={identityOf(agents, a.requestedBy)} size={26} />
              <span style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 1 }}>
                <span style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                  <span className="ell" style={{ fontSize: 13, fontWeight: 600, flex: 1 }}>
                    {a.title}
                  </span>
                  <span className="sub">{age(a.requestedAt)}</span>
                </span>
                <span className="sub ell">{canApprove ? `${a.requestedBy} · ${policyLine(a)}` : "Your role can't approve changes"}</span>
              </span>
              <Logo text={systemBadge(a.context.integration)} />
            </button>
          ))}
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center", padding: "10px 14px", borderTop: "1px solid var(--bs)" }} className="sub">
          <span className="kbd">J</span>
          <span className="kbd">K</span> move <span style={{ width: 6 }} />
          <span className="kbd">E</span> expand changes
        </div>
      </section>
      {sel && who ? (
        <section className="dpane" aria-label="Approval detail">
          <div className="scroll fade" key={sel.id} style={{ flex: 1 }}>
            <div className="dhead">
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span className={`pill ${sla?.breached ? "st-fail" : "st-wait"}`}>
                  <span className="dot" />
                  {sla?.breached ? sla.text : `Waiting on you · ${age(sel.requestedAt) || "now"}`}
                </span>
                <span style={{ flex: 1 }} />
                <button className="mlink" onClick={() => web(`/trust-safety?tab=approvals&id=${encodeURIComponent(sel.id)}`)}>
                  Open in Trust &amp; Safety ↗
                </button>
              </div>
              <h2>{sel.title}</h2>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--t2)" }}>
                <AgentAvatar id={who} size={18} />
                <span>
                  Requested by {sel.requestedBy}
                  {sel.description && sel.description !== sel.title ? ` · ${sel.description}` : ""}
                </span>
              </span>
            </div>
            <div style={{ padding: "16px 24px 24px", display: "flex", flexDirection: "column", gap: 14 }}>
              <div className="card" style={{ overflow: "hidden" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 14px" }}>
                  <Logo text={systemBadge(sel.context.integration) || "·"} style={{ width: 28, height: 28, fontSize: 10 }} />
                  <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
                    <span className="ell" style={{ fontSize: 14, fontWeight: 600 }}>
                      {subject || (meta.find((m) => m.term === "Action")?.value ?? "What happens if you approve")}
                    </span>
                    <span className="sub">
                      {fields.length ? `${fields.length} ${fields.length === 1 ? "field changes" : "fields change"}` : meta.find((m) => m.term === "Action")?.value || "Details weren't reported"}
                    </span>
                  </div>
                  {sel.context.runId ? (
                    <button className="link" onClick={() => web(`/runs/${encodeURIComponent(sel.context.runId!)}`)}>
                      View run ↗
                    </button>
                  ) : null}
                </div>
                {fields.length ? (
                  <table className="difft">
                    <thead>
                      <tr>
                        <th style={{ width: "36%" }}>Field</th>
                        <th>After approval</th>
                      </tr>
                    </thead>
                    <tbody>
                      {shownFields.map((r, i) => (
                        <tr key={i}>
                          <td>{r.term}</td>
                          <td>
                            <span className={`newp ${r.mono ? "mono" : ""}`}>{r.value}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : null}
                {fields.length > shownFields.length ? (
                  <button className="link" style={{ padding: "8px 14px", borderTop: "1px solid var(--bs)", width: "100%", textAlign: "left" }} onClick={() => setExpanded(true)}>
                    Show {fields.length - shownFields.length} more
                  </button>
                ) : null}
                {sel.steps.length ? (
                  <div style={{ borderTop: "1px solid var(--bs)", padding: "8px 14px", display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
                    {sel.steps.map((s, i) => (
                      <span key={i} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                        <span className="sub mono">{i + 1}</span>
                        <span style={{ flex: 1 }}>{s.text}</span>
                        {s.app ? <Logo text={systemBadge(s.app)} /> : null}
                        {s.access === "write" ? <span className="pill st-wait" style={{ height: 18, fontSize: 11 }}>Writes</span> : null}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
              <div className="card" style={{ overflow: "hidden" }}>
                <div className="sech" style={{ paddingBottom: 10 }}>
                  <h2>Why this needs approval</h2>
                </div>
                <div className="kv">
                  <span>Policy</span>
                  <span>{policyLine(sel)}</span>
                </div>
                <div className="kv">
                  <span>Who can approve</span>
                  <span>{approvers(sel, canApprove)}</span>
                </div>
                {sel.context.riskLevel ? (
                  <div className="kv">
                    <span>Risk</span>
                    <span>{titleCase(sel.context.riskLevel)}</span>
                  </div>
                ) : null}
                {meta
                  .filter((m) => m.term !== "Action")
                  .map((m) => (
                    <div key={m.term} className="kv">
                      <span>{m.term}</span>
                      {m.href ? (
                        <button className="link" style={{ justifySelf: "start", fontSize: 13 }} onClick={() => web(m.href!)}>
                          {m.value} ↗
                        </button>
                      ) : (
                        <span>{m.value}</span>
                      )}
                    </div>
                  ))}
                {convId ? (
                  <div className="kv">
                    <span>Conversation</span>
                    <button className="link" style={{ justifySelf: "start", fontSize: 13 }} onClick={() => go({ view: "ask", select: convId })}>
                      {convName}
                    </button>
                  </div>
                ) : null}
              </div>
              {rejecting ? (
                <div className="card fade" style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
                  <label htmlFor="rej" style={{ fontSize: 13, fontWeight: 600 }}>
                    Why are you rejecting this?
                  </label>
                  <textarea
                    id="rej"
                    rows={2}
                    autoFocus
                    className="field"
                    placeholder={`${sel.requestedBy} sees your reason and can replan`}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Escape") setRejecting(false)
                      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void reject(sel)
                    }}
                    style={{ height: "auto", padding: "8px 10px", resize: "none" }}
                  />
                  <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                    <button className="btn btn-q btn-sm" onClick={() => setRejecting(false)}>
                      Cancel
                    </button>
                    <button className="btn btn-dp btn-sm" disabled={busy} onClick={() => void reject(sel)}>
                      Reject
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
          <div className="dfoot">
            <span className="sub" style={{ flex: 1 }}>
              {canApprove ? lockNote(sel) : "Your role can't approve changes in this workspace. An admin can."}
            </span>
            <button className="btn btn-d btn-lg" disabled={busy || !canApprove} onClick={() => setRejecting(true)}>
              Reject <span className="kbd">R</span>
            </button>
            <button className="btn btn-p btn-lg" disabled={busy || !canApprove} onClick={() => approve(sel)}>
              Approve <span className="kbd">A</span>
            </button>
          </div>
        </section>
      ) : (
        <section className="dpane">
          {approvals.at ? <Empty art={ART.checklist} title="All clear" body="No decisions are waiting. New requests appear the moment an agent pauses for a person." /> : null}
        </section>
      )}
    </div>
  )
}
