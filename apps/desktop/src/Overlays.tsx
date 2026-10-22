import { useEffect, useMemo, useRef, useState } from "react"
import { useStore, type View } from "./store"
import { Avatar, Icon, Mark, MOD, SHIFT, type IconName } from "./ui"
import { avatarColor, initials, timeAgo } from "./lib/model"
import type { Conversation } from "./lib/api"
import { RichText } from "./components/RichText"
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
      <div className="pop menu fade" role="menu" style={{ left: 10, top: 56 }}>
        <div className="eyebrow" style={{ padding: "8px 10px" }}>
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
              <span style={{ width: 22, height: 22, borderRadius: 6, background: avatarColor(o.id), color: "#fff", fontSize: 11, fontWeight: 700, display: "inline-flex", alignItems: "center", justifyContent: "center" }} aria-hidden="true">
                {initials(o.name)}
              </span>
              <span style={{ flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{o.name}</span>
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
      <div className="pop menu fade" role="menu" style={{ left: 10, bottom: 56 }}>
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
          <Icon name="moon" />
          {dark ? "Light theme" : "Dark theme"}
        </button>
        <button className="mi" role="menuitem" onClick={() => web("/home")}>
          <Icon name="ext" />
          Open Gravitre on the web
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

export function Notifications() {
  const { approvals, assignments, go, setOverlay, api, toast, refresh } = useStore()
  const dayAgo = Date.now() - 24 * 3600 * 1000
  const items: { key: string; title: string; body: string; time: string; cls: string; icon: IconName; open: () => void; approve?: () => void }[] = [
    ...approvals.data.slice(0, 3).map((a) => ({
      key: a.id,
      title: "Approval needed",
      body: `${a.title} · ${a.requestedBy}`,
      time: timeAgo(a.requestedAt),
      cls: "st-wait",
      icon: "appr" as IconName,
      open: () => go({ view: "appr", select: a.id }),
      approve: () => {
        setOverlay(null)
        api
          .approve(a.id)
          .then(() => toast(`Approved · ${a.title}`))
          .catch((err) => toast(err instanceof Error ? err.message : "Couldn't approve", "error"))
          .finally(() => void refresh("approvals"))
      },
    })),
    ...assignments.data
      .filter((a) => (a.status === "done" || a.status === "failed") && new Date(a.finishedAt || a.createdAt).getTime() > dayAgo)
      .slice(0, 4)
      .map((a) => ({
        key: a.id,
        title: a.status === "done" ? "Assignment finished" : `Run failed: ${a.title}`,
        body: a.status === "done" ? `${a.title}${a.outcome && a.outcome !== "Finished." ? ` · ${a.outcome}` : ""}` : a.outcome || "Open it to see why.",
        time: timeAgo(a.finishedAt || a.createdAt),
        cls: a.status === "done" ? "st-done" : "st-fail",
        icon: (a.status === "done" ? "check" : "alert") as IconName,
        open: () => go({ view: "assign", select: a.id }),
      })),
  ]
  return (
    <>
      <Backdrop onClose={() => setOverlay(null)} />
      <div className="pop menu fade" role="dialog" aria-label="Notifications" style={{ right: 12, top: 48, width: 390, padding: 8 }}>
        <div style={{ display: "flex", alignItems: "center", padding: "8px 8px 10px" }}>
          <span style={{ fontSize: 15, fontWeight: 600, flex: 1 }}>Notifications</span>
          <button className="btn btn-l btn-sm" onClick={() => go("settings")}>
            Preferences
          </button>
        </div>
        {items.length === 0 ? (
          <div className="sub" style={{ padding: "12px 8px", borderTop: "1px solid var(--bs)" }}>
            Nothing new. Approvals and finished work from the last day show here.
          </div>
        ) : null}
        {items.map((n) => (
          <div key={n.key} style={{ display: "flex", gap: 10, padding: "12px 8px", borderTop: "1px solid var(--bs)" }}>
            <span className={`pill ${n.cls}`} style={{ width: 30, height: 30, padding: 0, justifyContent: "center", borderRadius: 9 }}>
              <Icon name={n.icon} size={14} />
            </span>
            <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
              <span style={{ fontSize: 13, fontWeight: 600 }}>{n.title}</span>
              <span style={{ fontSize: 13, color: "var(--t2)", overflow: "hidden", textOverflow: "ellipsis", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>{n.body}</span>
              <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                <button className="btn btn-sm" onClick={n.open}>
                  Open
                </button>
                {n.approve ? (
                  <button className="btn btn-k btn-sm" onClick={n.approve}>
                    Approve
                  </button>
                ) : null}
              </div>
            </div>
            <span className="sub">{n.time}</span>
          </div>
        ))}
      </div>
    </>
  )
}

type Cmd = { head?: string; t?: string; k?: string; icon?: IconName; run?: () => void }

export const VIEW_KEYS: [View, string, IconName, string][] = [
  ["home", "Home", "home", "1"],
  ["ask", "Ask", "ask", "2"],
  ["voice", "Voice", "voice", "3"],
  ["assign", "Assignments", "assign", "4"],
  ["appr", "Approvals", "appr", "5"],
  ["act", "Activity", "act", "6"],
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
      { t: dark ? "Switch to light theme" : "Switch to dark theme", icon: "moon" as IconName, run: () => (setPrefs({ theme: dark ? "light" : "dark" }), setOverlay(null)) },
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
  const { api, setOverlay, go, prefs } = useStore()
  const agent = useAgentName()
  const [draft, setDraft] = useState("")
  const [question, setQuestion] = useState("")
  const [answer, setAnswer] = useState("")
  const [status, setStatus] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const conv = useRef<string | null>(null)
  const input = useRef<HTMLInputElement>(null)

  const send = async () => {
    const t = draft.trim()
    if (!t || busy) return
    setDraft("")
    setQuestion(t)
    setAnswer("")
    setError(null)
    setBusy(true)
    try {
      if (!conv.current) conv.current = (await api.createConversation(t)).id
      const history = question && answer ? [{ role: "user" as const, text: question }, { role: "assistant" as const, text: answer }] : []
      const res = await api.chat({ history, message: t, conversationId: conv.current, agentId: prefs.agentId || null }, { onText: setAnswer, onStatus: setStatus })
      setAnswer(res.text || "Done.")
    } catch (err) {
      setError(err instanceof Error ? err.message : "The answer didn't come through.")
    } finally {
      setBusy(false)
      setStatus("")
      input.current?.focus()
    }
  }

  const pasteClipboard = async () => {
    try {
      const text = (await navigator.clipboard.readText()).trim()
      if (text) setDraft((d) => `${d ? `${d} ` : ""}${text.slice(0, 4000)}`)
    } catch {
      setError("Gravitre couldn't read the clipboard.")
    }
  }

  return (
    <div className="scrim" onClick={() => setOverlay(null)} style={{ background: "transparent", justifyContent: "flex-end", alignItems: "flex-start", padding: "56px 56px 0 0" }}>
      <div className="pop fade" role="dialog" aria-label="Quick Ask" style={{ width: 420, height: 520, display: "flex", flexDirection: "column", overflow: "hidden", background: "var(--cv)", borderRadius: 16 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ height: 44, display: "flex", alignItems: "center", gap: 10, padding: "0 8px 0 14px", background: "var(--s3)", borderBottom: "1px solid var(--bd)", flex: "none" }}>
          <Mark width={20} height={12} />
          <span style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>Quick Ask</span>
          <button aria-label="Close" className="ib" onClick={() => setOverlay(null)}>
            <Icon name="x" />
          </button>
        </div>
        <div style={{ flex: 1, overflow: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          {!question ? (
            <div style={{ margin: "auto", textAlign: "center", display: "flex", flexDirection: "column", gap: 6, maxWidth: 300 }}>
              <span className="eyebrow">From any app</span>
              <span style={{ fontSize: 18, fontWeight: 600 }}>Ask without switching windows</span>
              <span className="sub">
                Paste your clipboard into the question. Press {MOD}
                {SHIFT}Space anywhere.
              </span>
            </div>
          ) : (
            <div className="ubub">{question}</div>
          )}
          {question ? (
            <div style={{ display: "flex", gap: 10 }} className="fade">
              <Avatar name={agent} size={24} />
              <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 0 }}>
                {busy && !answer ? (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--sig)" }}>
                    <span className="typing">
                      <span />
                      <span />
                      <span />
                    </span>
                    {status || "Checking your sources"}
                  </span>
                ) : null}
                {answer ? <RichText text={answer} size={14} /> : null}
                {error ? <span style={{ fontSize: 13, color: "var(--dgk)" }}>{error}</span> : null}
                {answer && !busy ? (
                  <button className="btn btn-l btn-sm" style={{ alignSelf: "flex-start", padding: 0 }} onClick={() => go({ view: "ask", select: conv.current })}>
                    Continue in full window →
                  </button>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
        <div style={{ padding: "10px 12px 12px" }}>
          <div className="composer">
            <label htmlFor="qa" className="sr">
              Quick Ask
            </label>
            <input
              id="qa"
              ref={input}
              className="ta"
              autoFocus
              placeholder={`Ask ${agent}`}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void send()
                if (e.key === "Escape") setOverlay(null)
              }}
            />
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <button className="ib" aria-label="Paste clipboard" title="Paste clipboard" style={{ width: 30, height: 30 }} onClick={() => void pasteClipboard()}>
                <Icon name="clip" />
              </button>
              <span style={{ flex: 1 }} />
              <div className="mode" role="radiogroup" aria-label="Conversation mode">
                <button className="on" role="radio" aria-checked="true">
                  Text
                </button>
                <button role="radio" aria-checked="false" onClick={() => go("voice")}>
                  Voice
                </button>
              </div>
              <button className="btn btn-k btn-sm" disabled={busy || !draft.trim()} onClick={() => void send()}>
                Ask ↵
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
