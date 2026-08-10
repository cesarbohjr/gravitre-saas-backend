import { useCallback, useEffect, useMemo, useState } from "react"
import {
  decideApproval,
  fetchActivity,
  fetchApprovals,
  openDeepLink,
  sendChat,
  type ActivityEvent,
  type ApprovalItem,
} from "./lib/api"
import {
  clearSession,
  loadSession,
  parseAuthDeepLink,
  saveSession,
  type DesktopSession,
} from "./lib/session"

type Tab = "chat" | "activity" | "approvals"
type Modality = "text" | "voice"

type ChatMessage = {
  id: string
  role: "user" | "assistant"
  text: string
}

const CONNECT_URL = "https://gravitre.app/desktop/connect"

export default function App() {
  const [session, setSession] = useState<DesktopSession | null>(() => loadSession())
  const [tab, setTab] = useState<Tab>("chat")
  const [modality, setModality] = useState<Modality>("text")
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [activity, setActivity] = useState<ActivityEvent[]>([])
  const [approvals, setApprovals] = useState<ApprovalItem[]>([])

  const connected = Boolean(session?.accessToken && session.orgId)

  const applySession = useCallback((next: DesktopSession) => {
    saveSession(next)
    setSession(next)
  }, [])

  useEffect(() => {
    let unlisten: (() => void) | undefined
    ;(async () => {
      try {
        const { onOpenUrl } = await import("@tauri-apps/plugin-deep-link")
        unlisten = await onOpenUrl((urls) => {
          for (const url of urls) {
            const parsed = parseAuthDeepLink(url)
            if (parsed) applySession(parsed)
          }
        })
      } catch {
        // Browser/dev preview — deep links unavailable.
      }
    })()
    return () => {
      unlisten?.()
    }
  }, [applySession])

  const refreshSidePanels = useCallback(async () => {
    if (!session) return
    try {
      const [events, pending] = await Promise.all([
        fetchActivity(session),
        fetchApprovals(session),
      ])
      setActivity(events)
      setApprovals(pending)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh")
    }
  }, [session])

  useEffect(() => {
    if (!session) return
    void refreshSidePanels()
    const id = window.setInterval(() => void refreshSidePanels(), 30_000)
    return () => window.clearInterval(id)
  }, [session, refreshSidePanels])

  useEffect(() => {
    if (!session || approvals.length === 0) return
    ;(async () => {
      try {
        const { isPermissionGranted, requestPermission, sendNotification } = await import(
          "@tauri-apps/plugin-notification"
        )
        let granted = await isPermissionGranted()
        if (!granted) {
          const permission = await requestPermission()
          granted = permission === "granted"
        }
        if (!granted) return
        const first = approvals[0]
        sendNotification({
          title: "Approval needed",
          body: first.title || first.summary || "A Gravitre action is waiting for approval.",
        })
      } catch {
        // Notifications require the native shell.
      }
    })()
  }, [approvals, session])

  const statusLabel = useMemo(() => {
    if (!session) return "Signed out"
    return `Org ${session.orgId.slice(0, 8)}…`
  }, [session])

  const onSend = async () => {
    if (!session || !input.trim() || busy) return
    const text = input.trim()
    setInput("")
    setBusy(true)
    setError(null)
    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: "user", text }
    setMessages((prev) => [...prev, userMsg])
    try {
      const reply = await sendChat(session, text, modality === "voice")
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "assistant", text: reply },
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed")
    } finally {
      setBusy(false)
    }
  }

  const onApprove = async (item: ApprovalItem, decision: "approve" | "reject") => {
    if (!session) return
    const runId = item.run_id || item.runId || item.id
    if (!runId) return
    setBusy(true)
    setError(null)
    try {
      await decideApproval(session, runId, decision)
      await refreshSidePanels()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Decision failed")
    } finally {
      setBusy(false)
    }
  }

  if (!connected) {
    return (
      <div className="auth">
        <h1>Gravitre</h1>
        <p className="muted">
          Desktop companion — chat, glanceable activity, and approvals. Settings, Meson, Agents,
          and Billing open in your browser.
        </p>
        <button
          className="btn"
          type="button"
          onClick={() => void openDeepLink("/desktop/connect")}
        >
          Connect with browser session
        </button>
        <p className="muted">
          Opens {CONNECT_URL}. Uses your existing gravitre.app login — no second account.
        </p>
        <button
          className="btn ghost"
          type="button"
          onClick={() => {
            const sample = window.prompt("Paste gravitre://auth… deep link (dev)")
            if (!sample) return
            const parsed = parseAuthDeepLink(sample)
            if (parsed) applySession(parsed)
            else setError("Could not parse auth deep link")
          }}
        >
          Paste auth link (dev)
        </button>
        {error ? <p className="muted">{error}</p> : null}
      </div>
    )
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">Gravitre</div>
        <span className={`pill ${connected ? "ok" : ""}`}>{statusLabel}</span>
        <button
          className="btn ghost"
          type="button"
          onClick={() => {
            clearSession()
            setSession(null)
          }}
        >
          Sign out
        </button>
      </header>

      <nav className="tabs">
        {(
          [
            ["chat", "Chat"],
            ["activity", "Activity"],
            ["approvals", "Approvals"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`tab ${tab === id ? "active" : ""}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      <main className="main">
        {error ? <p className="muted">{error}</p> : null}

        {tab === "chat" ? (
          <>
            <div className="modality">
              <button
                type="button"
                className={modality === "text" ? "active" : ""}
                onClick={() => setModality("text")}
              >
                Text
              </button>
              <button
                type="button"
                className={modality === "voice" ? "active" : ""}
                onClick={() => setModality("voice")}
              >
                Voice
              </button>
            </div>
            {modality === "voice" ? (
              <div className={`wave ${busy ? "live" : ""}`} aria-hidden>
                {Array.from({ length: 7 }).map((_, i) => (
                  <span key={i} style={{ animationDelay: `${i * 0.08}s`, height: "40%" }} />
                ))}
              </div>
            ) : null}
            <div className="messages">
              {messages.length === 0 ? (
                <p className="muted">Ask anything. Press Alt+Space (Option+Space on Mac) anytime.</p>
              ) : null}
              {messages.map((msg) => (
                <div key={msg.id} className={`bubble ${msg.role}`}>
                  {msg.text}
                </div>
              ))}
            </div>
          </>
        ) : null}

        {tab === "activity" ? (
          <div className="list">
            {activity.length === 0 ? (
              <p className="muted">No recent activity yet.</p>
            ) : (
              activity.map((event, index) => (
                <button
                  key={event.id || `${index}`}
                  type="button"
                  className="card"
                  onClick={() => void openDeepLink(event.href || "/activity")}
                >
                  <h3>{event.title || "Activity"}</h3>
                  <p>{event.summary || event.source || "Open in web for detail"}</p>
                </button>
              ))
            )}
            <button className="btn ghost" type="button" onClick={() => void openDeepLink("/activity")}>
              Open full Activity
            </button>
          </div>
        ) : null}

        {tab === "approvals" ? (
          <div className="list">
            {approvals.length === 0 ? (
              <p className="muted">No pending approvals.</p>
            ) : (
              approvals.map((item, index) => {
                const runId = item.run_id || item.runId || item.id || `${index}`
                return (
                  <div key={runId} className="card">
                    <h3>{item.title || "Pending approval"}</h3>
                    <p>{item.summary || "Approve or reject without leaving your current app."}</p>
                    <div className="card-actions">
                      <button
                        className="btn"
                        type="button"
                        disabled={busy}
                        onClick={() => void onApprove(item, "approve")}
                      >
                        Approve
                      </button>
                      <button
                        className="btn danger"
                        type="button"
                        disabled={busy}
                        onClick={() => void onApprove(item, "reject")}
                      >
                        Reject
                      </button>
                      <button
                        className="btn ghost"
                        type="button"
                        onClick={() => void openDeepLink(`/approvals?id=${encodeURIComponent(runId)}`)}
                      >
                        Details
                      </button>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        ) : null}
      </main>

      {tab === "chat" ? (
        <footer className="composer">
          <div className="composer-row">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={modality === "voice" ? "Speak or type…" : "Message Gravitre…"}
              rows={2}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  void onSend()
                }
              }}
            />
            <button className="btn" type="button" disabled={busy || !input.trim()} onClick={() => void onSend()}>
              {busy ? "…" : "Send"}
            </button>
          </div>
        </footer>
      ) : null}
    </div>
  )
}
