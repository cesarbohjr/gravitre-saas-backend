import { useEffect, useMemo, useRef, useState } from "react"
import { useStore, type View } from "./store"
import { AgentAvatar, Icon, MarkTile, MOD, SHIFT, WorkspaceTile, type IconName } from "./ui"
import { timeAgo } from "./lib/model"
import type { Conversation } from "./lib/api"
import { RichText } from "./components/RichText"
import { AgentChip, clipboardAttachment, Composer, withAttachments, type Attachment } from "./components/Composer"
import { identityOf } from "./lib/identity"
import { systemBadge } from "./lib/model"
import { Logo } from "./ui"
import type { ContextSourcesSummary } from "@web/lib/context-sources"
import { useAgentName } from "./views/Voice"

function Backdrop({ onClose }: { onClose: () => void }) {
  return <div style={{ position: "absolute", inset: 0, zIndex: 45 }} onClick={onClose} />
}

export function WorkspaceMenu() {
  const { me, session, switchWorkspace, setOverlay, web, toast } = useStore()
  const orgs = me?.organizations ?? []
  return (
    <>
      <Backdrop onClose={() => setOverlay(null)} />
      <div className="pop menu fade" role="menu" aria-label="Workspaces" style={{ left: 10, bottom: 100 }}>
        <div className="eyebrow" style={{ padding: "6px 10px" }}>
          Workspaces
        </div>
        {orgs.length === 0 ? (
          <div className="sub" style={{ padding: "6px 10px" }}>
            Loading…
          </div>
        ) : null}
        {orgs.map((o) => {
          const on = o.id === session.orgId
          return (
            <button
              key={o.id}
              className={`mi ${on ? "on" : ""}`}
              role="menuitemradio"
              aria-checked={on}
              onClick={() => {
                if (!on) {
                  switchWorkspace(o.id)
                  toast(`Switched to ${o.name}`)
                } else setOverlay(null)
              }}
            >
              <WorkspaceTile name={o.name} size={22} />
              <span className="ell" style={{ flex: 1 }}>
                {o.name}
              </span>
              <span className="sub">{o.role ? o.role.charAt(0).toUpperCase() + o.role.slice(1) : ""}</span>
            </button>
          )
        })}
        <div style={{ borderTop: "1px solid var(--bs)", marginTop: 6, paddingTop: 6 }}>
          <button className="mi" style={{ color: "var(--t2)" }} onClick={() => web("/settings/organizations")}>
            Manage workspaces on web ↗
          </button>
        </div>
      </div>
    </>
  )
}

export function UserMenu() {
  const { me, dark, setPrefs, go, setOverlay, web, signOut } = useStore()
  return (
    <>
      <Backdrop onClose={() => setOverlay(null)} />
      <div className="pop menu fade" role="menu" aria-label="Account" style={{ left: 10, bottom: 54 }}>
        <div style={{ padding: "8px 10px", display: "flex", flexDirection: "column" }}>
          <span style={{ fontSize: 14, fontWeight: 600 }}>{me?.name || "Signed in"}</span>
          <span className="sub">{[me?.email, me?.role ? me.role.charAt(0).toUpperCase() + me.role.slice(1) : null].filter(Boolean).join(" · ")}</span>
        </div>
        <button className="mi" role="menuitem" onClick={() => go("settings")}>
          <Icon name="settings" />
          <span style={{ flex: 1 }}>Settings</span>
          <span className="kbd">{MOD} ,</span>
        </button>
        <button
          className="mi"
          role="menuitem"
          onClick={() => {
            setPrefs({ theme: dark ? "light" : "dark" })
            setOverlay(null)
          }}
        >
          <Icon name="circle" />
          {dark ? "Light theme" : "Dark theme"}
        </button>
        <button className="mi" role="menuitem" onClick={() => web("/settings/profile")}>
          <Icon name="ext" />
          Account on the web
        </button>
        <div style={{ borderTop: "1px solid var(--bs)", margin: "6px 0" }} />
        <button className="mi" role="menuitem" onClick={signOut}>
          <Icon name="logout" />
          Sign out
        </button>
      </div>
    </>
  )
}

/** In-app copies of the native notifications, with the buttons the OS ones can't carry. */
export function Notices() {
  const { notices, dismissNotice, go, approveWithUndo, canApprove } = useStore()
  if (!notices.length) return null
  return (
    <div className="notices" aria-live="polite">
      {notices.map((n) => (
        <div key={n.id} className="notice fade" role="status">
          <MarkTile size={30} />
          <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
            <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
              <span style={{ fontSize: 13, fontWeight: 600, flex: 1 }} className="ell">
                {n.title}
              </span>
              <span className="sub">{n.time}</span>
            </div>
            <span style={{ fontSize: 13, color: "var(--t2)" }}>{n.body}</span>
            <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
              <button
                className="btn btn-sm"
                onClick={() => {
                  dismissNotice(n.id)
                  go(n.open)
                }}
              >
                Open
              </button>
              {n.approval && canApprove ? (
                <button
                  className="btn btn-p btn-sm"
                  onClick={() => {
                    dismissNotice(n.id)
                    approveWithUndo(n.approval!)
                  }}
                >
                  Approve
                </button>
              ) : null}
            </div>
          </div>
          <button className="ib" aria-label="Dismiss" style={{ width: 24, height: 24 }} onClick={() => dismissNotice(n.id)}>
            <Icon name="x" size={13} />
          </button>
        </div>
      ))}
    </div>
  )
}

type Cmd = { head?: string; t?: string; k?: string; icon?: IconName; run?: () => void }

export const VIEW_KEYS: [View, string, IconName, string][] = [
  ["home", "Home", "home", "1"],
  ["ask", "Ask", "ask", "2"],
  ["assign", "Assignments", "assign", "3"],
  ["appr", "Approvals", "appr", "4"],
  ["act", "Activity", "act", "5"],
  ["voice", "Voice", "voice", "6"],
]

export function CommandBar() {
  const { go, setOverlay, setPrefs, dark, approvals, assignments, api } = useStore()
  const agent = useAgentName()
  const [q, setQ] = useState("")
  const [convs, setConvs] = useState<Conversation[]>([])
  const [active, setActive] = useState(0)

  useEffect(() => {
    const t = window.setTimeout(() => {
      api
        .conversations(q)
        .then((rows) => setConvs(rows.slice(0, 8)))
        .catch(() => setConvs([]))
    }, 180)
    return () => window.clearTimeout(t)
  }, [api, q])

  const cmds: Cmd[] = useMemo(
    () => [
      { head: "Go to" },
      ...VIEW_KEYS.map(([v, t, icon, n]) => ({ t, k: `${MOD} ${n}`, icon, run: () => go(v) })),
      { t: "Settings", k: `${MOD} ,`, icon: "settings" as IconName, run: () => go("settings") },
      { head: "Actions" },
      { t: "New conversation", k: `${MOD} N`, icon: "plus" as IconName, run: () => go({ view: "ask", select: null }) },
      { t: "Quick Ask", k: `${MOD}${SHIFT}Space`, icon: "ask" as IconName, run: () => setOverlay("quick") },
      { t: dark ? "Switch to light theme" : "Switch to dark theme", icon: "circle" as IconName, run: () => (setPrefs({ theme: dark ? "light" : "dark" }), setOverlay(null)) },
      ...(approvals.data.length ? [{ head: "Waiting on you" }] : []),
      ...approvals.data.slice(0, 5).map((a) => ({ t: a.title, k: "Approval", icon: "appr" as IconName, run: () => go({ view: "appr", select: a.id }) })),
      ...(assignments.data.length ? [{ head: "Assignments" }] : []),
      ...assignments.data.slice(0, 5).map((a) => ({ t: a.title, k: a.agent, icon: "assign" as IconName, run: () => go({ view: "assign", select: a.id }) })),
      ...(convs.length ? [{ head: "Conversations" }] : []),
      ...convs.map((c) => ({ t: c.title, k: timeAgo(c.updatedAt), icon: "ask" as IconName, run: () => go({ view: "ask", select: c.id }) })),
    ],
    [approvals.data, assignments.data, convs, dark, go, setOverlay, setPrefs],
  )
  const needle = q.trim().toLowerCase()
  // Conversations are already filtered by the server search, so keep them all.
  const shown = needle
    ? cmds.filter((c, i) => {
        if (c.head) return false
        const conv = i >= cmds.length - convs.length
        return conv || (c.t || "").toLowerCase().includes(needle)
      })
    : cmds
  const runnable = shown.filter((c) => c.run)

  useEffect(() => setActive(0), [q])

  const askInstead = () => go({ view: "ask", ask: q.trim(), select: null })

  return (
    <div className="scrim" onClick={() => setOverlay(null)}>
      <div className="pop fade" role="dialog" aria-label="Command bar" style={{ width: 620, overflow: "hidden", borderRadius: 16 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, height: 56, padding: "0 16px", borderBottom: "1px solid var(--bs)" }}>
          <Icon name="search" style={{ color: "var(--t3)" }} />
          <label htmlFor="cmdq" className="sr">
            Search or run a command
          </label>
          <input
            id="cmdq"
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") setOverlay(null)
              if (e.key === "ArrowDown") (e.preventDefault(), setActive((a) => Math.min(a + 1, runnable.length - 1)))
              if (e.key === "ArrowUp") (e.preventDefault(), setActive((a) => Math.max(a - 1, 0)))
              if (e.key === "Enter") {
                const hit = runnable[active]
                if (hit?.run) hit.run()
                else if (q.trim()) askInstead()
              }
            }}
            placeholder="Search conversations, approvals, assignments, or jump anywhere"
            style={{ flex: 1, border: 0, outline: "none", background: "transparent", fontSize: 16 }}
          />
          <span className="kbd">Esc</span>
        </div>
        <div style={{ padding: 6, maxHeight: 400, overflow: "auto" }}>
          {shown.map((c, i) =>
            c.head ? (
              <div key={`h${i}`} className="eyebrow" style={{ padding: "10px 10px 4px" }}>
                {c.head}
              </div>
            ) : (
              <button key={`c${i}`} className={`mi ${runnable[active] === c ? "on" : ""}`} onClick={c.run} onMouseEnter={() => setActive(runnable.indexOf(c))}>
                <Icon name={c.icon || "dot"} style={{ color: "var(--t3)" }} />
                <span style={{ flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{c.t}</span>
                <span className="sub">{c.k}</span>
              </button>
            ),
          )}
          {needle && runnable.length === 0 ? (
            <button className="mi" onClick={askInstead}>
              <Icon name="ask" style={{ color: "var(--br)" }} />
              <span style={{ flex: 1 }}>
                Ask {agent}: “{q.trim()}”
              </span>
              <span className="sub">↵</span>
            </button>
          ) : null}
        </div>
      </div>
    </div>
  )
}

export function QuickAsk() {
  const { api, setOverlay, go, prefs, agents, toast } = useStore()
  const agent = identityOf(agents, null, prefs.agentId || null)
  const [draft, setDraft] = useState("")
  const [turns, setTurns] = useState<{ q: string; a: string; sources: ContextSourcesSummary | null }[]>([])
  const [status, setStatus] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const conv = useRef<string | null>(null)
  const abort = useRef<AbortController | null>(null)
  const scroller = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight })
  }, [turns])

  const send = async () => {
    const t = draft.trim()
    if (!t || busy) return
    const message = withAttachments(t, attachments)
    setDraft("")
    setAttachments([])
    setError(null)
    setBusy(true)
    const history = turns.flatMap((x) => [
      { role: "user" as const, text: x.q },
      { role: "assistant" as const, text: x.a },
    ])
    setTurns((prev) => [...prev, { q: t, a: "", sources: null }])
    const patch = (p: { a?: string; sources?: ContextSourcesSummary | null }) =>
      setTurns((prev) => prev.map((x, i) => (i === prev.length - 1 ? { ...x, ...p } : x)))
    abort.current = new AbortController()
    try {
      if (!conv.current) conv.current = (await api.createConversation(t)).id
      const res = await api.chat(
        { history, message, conversationId: conv.current, agentId: prefs.agentId || null },
        { onText: (a) => patch({ a }), onStatus: setStatus },
        abort.current.signal,
      )
      patch({ a: res.text || "Done.", sources: res.sources })
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) setError(err instanceof Error ? err.message : "The answer didn't come through.")
    } finally {
      abort.current = null
      setBusy(false)
      setStatus("")
    }
  }

  const attach = async () => {
    const a = await clipboardAttachment()
    if (a === "denied") toast("Gravitre couldn't read the clipboard.", "error")
    else if (!a) toast("The clipboard is empty.", "error")
    else setAttachments((prev) => [...prev, a])
  }

  return (
    <div className="scrim" onClick={() => setOverlay(null)} style={{ background: "transparent", justifyContent: "flex-end", alignItems: "flex-start", padding: "16px 16px 0 0" }}>
      <div className="pop fade" role="dialog" aria-label="Quick Ask" style={{ width: 380, height: 470, display: "flex", flexDirection: "column", overflow: "hidden", background: "var(--cv)", borderRadius: 12 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ height: 40, display: "flex", alignItems: "center", gap: 8, padding: "0 6px 0 12px", background: "var(--s1)", borderBottom: "1px solid var(--bd)", flex: "none" }}>
          <MarkTile size={20} />
          <span style={{ fontSize: 13, fontWeight: 600, flex: 1 }}>Quick Ask</span>
          <button aria-label="Continue in full window" title="Continue in full window" className="ib" style={{ width: 28, height: 28 }} onClick={() => go({ view: "ask", select: conv.current })}>
            <Icon name="expand" size={14} />
          </button>
          <button aria-label="Close" className="ib" style={{ width: 28, height: 28 }} onClick={() => setOverlay(null)}>
            <Icon name="x" size={14} />
          </button>
        </div>
        <div ref={scroller} style={{ flex: 1, overflow: "auto", padding: 12, display: "flex", flexDirection: "column", gap: 12 }}>
          {!turns.length ? (
            <div style={{ margin: "auto", textAlign: "center", display: "flex", flexDirection: "column", gap: 4, maxWidth: 280 }}>
              <span style={{ fontSize: 15, fontWeight: 600 }}>Ask without switching windows</span>
              <span className="sub">
                Attach your clipboard with the clip button. Press {MOD}
                {SHIFT}Space from any app.
              </span>
            </div>
          ) : null}
          {turns.map((x, i) => (
            <div key={i} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div className="ubub" style={{ fontSize: 13 }}>
                {x.q}
              </div>
              <div style={{ display: "flex", gap: 8 }} className="fade">
                <AgentAvatar id={agent} size={22} />
                <div style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 0, flex: 1 }}>
                  <span style={{ fontSize: 13 }}>
                    <b>{agent.name}</b> <span className="sub">{agent.dept.id !== "general" ? agent.dept.label : ""}</span>
                  </span>
                  {busy && i === turns.length - 1 && !x.a ? (
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--sig)" }}>
                      <span className="typing">
                        <span />
                        <span />
                        <span />
                      </span>
                      {status || "Checking your sources"}
                    </span>
                  ) : null}
                  {x.a ? <RichText text={x.a} size={13} /> : null}
                  {x.sources?.used.length ? (
                    <span className="sub" style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                      {x.sources.used.slice(0, 2).map((u, j) => (
                        <span key={j} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                          <Logo text={systemBadge(u.kind) || "·"} style={{ width: 16, height: 16, fontSize: 7 }} />
                          {u.name}
                          {u.freshness ? ` · ${u.freshness}` : ""}
                        </span>
                      ))}
                    </span>
                  ) : null}
                  {x.a && !(busy && i === turns.length - 1) && i === turns.length - 1 ? (
                    <button className="link" style={{ alignSelf: "flex-start" }} onClick={() => go({ view: "ask", select: conv.current })}>
                      Continue in full window
                    </button>
                  ) : null}
                </div>
              </div>
            </div>
          ))}
          {error ? <span style={{ fontSize: 13, color: "var(--dgk)" }}>{error}</span> : null}
        </div>
        <div style={{ padding: "8px 10px 10px" }}>
          <Composer
            id="qa"
            autoFocus
            value={draft}
            onChange={setDraft}
            onSend={() => void send()}
            placeholder={turns.length ? "Ask a follow-up" : `Ask ${agent.name}`}
            busy={busy}
            onStop={() => abort.current?.abort()}
            onVoice={() => go("voice")}
            attachments={attachments}
            onAttach={() => void attach()}
            onRemove={(id) => setAttachments((prev) => prev.filter((a) => a.id !== id))}
            leading={<AgentChip />}
          />
        </div>
      </div>
    </div>
  )
}
