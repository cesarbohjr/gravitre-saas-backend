import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  decideApproval,
  fetchVoiceStatus,
  fetchActivity,
  fetchApprovals,
  openDeepLink,
  sendChat,
  synthesizeVoiceReply,
  type ActivityEvent,
  type DesktopChatTurn,
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
  const [voiceEntitled, setVoiceEntitled] = useState(true)
  const [voiceUnavailableReason, setVoiceUnavailableReason] = useState<string | null>(null)
  const [voiceListening, setVoiceListening] = useState(false)
  const [voiceSpeaking, setVoiceSpeaking] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const audioUrlRef = useRef<string | null>(null)
  const speechRecognitionRef = useRef<any>(null)

  const connected = Boolean(session?.accessToken && session.orgId)

  const applySession = useCallback((next: DesktopSession) => {
    saveSession(next)
    setSession(next)
  }, [])

  const stopVoicePlayback = useCallback(() => {
    if (audioRef.current) {
      try {
        audioRef.current.pause()
      } catch {
        // noop
      }
      audioRef.current.src = ""
      audioRef.current = null
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current)
      audioUrlRef.current = null
    }
    setVoiceSpeaking(false)
  }, [])

  const stopVoiceListening = useCallback(() => {
    const rec = speechRecognitionRef.current
    if (rec) {
      try {
        rec.stop()
      } catch {
        // noop
      }
    }
    setVoiceListening(false)
  }, [])

  const playVoiceReply = useCallback(
    async (replyText: string) => {
      if (!session || !voiceEntitled) return
      const text = String(replyText || "").trim()
      if (!text) return
      stopVoicePlayback()
      const blob = await synthesizeVoiceReply(session, text)
      const objectUrl = URL.createObjectURL(blob)
      const audio = new Audio(objectUrl)
      audioRef.current = audio
      audioUrlRef.current = objectUrl
      setVoiceSpeaking(true)
      audio.onended = () => stopVoicePlayback()
      audio.onerror = () => {
        stopVoicePlayback()
        setError("Voice playback failed")
      }
      await audio.play()
    },
    [session, stopVoicePlayback, voiceEntitled],
  )

  useEffect(() => {
    const cleanups: Array<() => void> = []
    ;(async () => {
      try {
        const { onOpenUrl } = await import("@tauri-apps/plugin-deep-link")
        const unlistenAuth = await onOpenUrl((urls) => {
          for (const url of urls) {
            const parsed = parseAuthDeepLink(url)
            if (parsed) applySession(parsed)
          }
        })
        cleanups.push(unlistenAuth)
      } catch {
        // Browser/dev preview — deep links unavailable.
      }

      try {
        const { listen } = await import("@tauri-apps/api/event")
        const { invoke } = await import("@tauri-apps/api/core")
        const unlistenSummon = await listen("companion-summoned", async () => {
          // Yield to paint, then focus the composer and report input-ready latency.
          await new Promise((r) => requestAnimationFrame(() => r(null)))
          const el = document.querySelector<HTMLTextAreaElement>("textarea")
          el?.focus()
          const ms = await invoke<number>("report_input_ready")
          if (ms > 0) {
            console.info(`[gravitre-desktop] summon_to_input_ready_ms=${ms}`)
            ;(window as unknown as { __gravitreSummonMs?: number }).__gravitreSummonMs = ms
          }
        })
        cleanups.push(unlistenSummon)
      } catch {
        // Native shell only.
      }
    })()
    return () => {
      for (const stop of cleanups) stop()
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
    if (!session) {
      setVoiceEntitled(true)
      setVoiceUnavailableReason(null)
      return
    }
    let cancelled = false
    void fetchVoiceStatus(session)
      .then((status) => {
        if (cancelled) return
        setVoiceEntitled(Boolean(status.enabled))
        setVoiceUnavailableReason(status.enabled ? null : status.reason || "Voice unavailable right now.")
      })
      .catch(() => {
        if (cancelled) return
        // Keep voice available when status check fails transiently.
        setVoiceEntitled(true)
        setVoiceUnavailableReason(null)
      })
    return () => {
      cancelled = true
    }
  }, [session])

  useEffect(() => {
    return () => {
      stopVoiceListening()
      stopVoicePlayback()
    }
  }, [stopVoiceListening, stopVoicePlayback])

  useEffect(() => {
    if (tab === "chat") return
    stopVoiceListening()
    stopVoicePlayback()
  }, [tab, stopVoiceListening, stopVoicePlayback])

  useEffect(() => {
    if (voiceEntitled || modality !== "voice") return
    setModality("text")
    stopVoiceListening()
    stopVoicePlayback()
  }, [modality, stopVoiceListening, stopVoicePlayback, voiceEntitled])

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

  const toggleVoiceListening = useCallback(() => {
    if (!voiceEntitled || modality !== "voice") return
    const Ctor =
      (window as unknown as { SpeechRecognition?: any; webkitSpeechRecognition?: any })
        .SpeechRecognition ||
      (window as unknown as { SpeechRecognition?: any; webkitSpeechRecognition?: any })
        .webkitSpeechRecognition
    if (!Ctor) {
      setError("Voice input is not supported in this desktop runtime.")
      return
    }
    let rec = speechRecognitionRef.current
    if (!rec) {
      rec = new Ctor()
      rec.lang = "en-US"
      rec.continuous = false
      rec.interimResults = false
      rec.onresult = (event: any) => {
        const transcript = String(event?.results?.[0]?.[0]?.transcript || "").trim()
        if (!transcript) return
        setInput((prev) => {
          const current = prev.trim()
          return current ? `${current} ${transcript}` : transcript
        })
      }
      rec.onerror = () => {
        setVoiceListening(false)
        setError("Microphone capture failed")
      }
      rec.onend = () => {
        setVoiceListening(false)
      }
      speechRecognitionRef.current = rec
    }
    if (voiceListening) {
      stopVoiceListening()
      return
    }
    try {
      rec.start()
      setVoiceListening(true)
      setError(null)
    } catch {
      setError("Could not start microphone")
    }
  }, [modality, stopVoiceListening, voiceEntitled, voiceListening])

  const onSend = async () => {
    if (!session || !input.trim() || busy) return
    const text = input.trim()
    stopVoiceListening()
    setInput("")
    setBusy(true)
    setError(null)
    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: "user", text }
    setMessages((prev) => [...prev, userMsg])
    try {
      const history: DesktopChatTurn[] = messages
        .filter((row) => row.role === "user" || row.role === "assistant")
        .map((row) => ({ role: row.role, text: row.text }))
      const reply = await sendChat(session, text, modality === "voice", history)
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "assistant", text: reply },
      ])
      if (modality === "voice" && voiceEntitled) {
        await playVoiceReply(reply)
      }
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
            stopVoiceListening()
            stopVoicePlayback()
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
                onClick={() => {
                  setModality("text")
                  stopVoiceListening()
                  stopVoicePlayback()
                }}
              >
                Text
              </button>
              <button
                type="button"
                className={modality === "voice" ? "active" : ""}
                disabled={!voiceEntitled}
                title={!voiceEntitled && voiceUnavailableReason ? voiceUnavailableReason : "Voice mode"}
                onClick={() => {
                  if (!voiceEntitled) {
                    if (voiceUnavailableReason) setError(voiceUnavailableReason)
                    return
                  }
                  setModality("voice")
                }}
              >
                Voice
              </button>
            </div>
            {!voiceEntitled && voiceUnavailableReason ? (
              <p className="muted">{voiceUnavailableReason}</p>
            ) : null}
            {modality === "voice" ? (
              <div className={`wave ${busy || voiceListening || voiceSpeaking ? "live" : ""}`} aria-hidden>
                {Array.from({ length: 7 }).map((_, i) => (
                  <span key={i} style={{ animationDelay: `${i * 0.08}s`, height: "40%" }} />
                ))}
              </div>
            ) : null}
            {modality === "voice" && voiceEntitled ? (
              <div className="voice-controls">
                <button
                  className={`btn ghost ${voiceListening ? "active" : ""}`}
                  type="button"
                  onClick={toggleVoiceListening}
                  disabled={busy}
                >
                  {voiceListening ? "Stop mic" : "Start mic"}
                </button>
                <button
                  className="btn ghost"
                  type="button"
                  onClick={stopVoicePlayback}
                  disabled={!voiceSpeaking}
                >
                  Stop audio
                </button>
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
