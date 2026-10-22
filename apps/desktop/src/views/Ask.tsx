import { useCallback, useEffect, useRef, useState } from "react"
import { ART } from "../art"
import type { ContextSourcesSummary } from "@web/lib/context-sources"
import { useStore } from "../store"
import { Art, Avatar, ErrorLine, Icon, Logo } from "../ui"
import { systemBadge, timeAgo } from "../lib/model"
import type { Conversation, PendingTask } from "../lib/api"
import { RichText } from "../components/RichText"
import { STARTERS } from "./Home"
import { useAgentName, VoiceStage } from "./Voice"

type Msg = {
  id: string
  role: "user" | "assistant"
  text: string
  thinking?: boolean
  status?: string
  sources?: ContextSourcesSummary | null
  pending?: PendingTask | null
  error?: string
}

let seq = 0
const mid = () => `m${Date.now()}-${seq++}`

function Sources({ s }: { s: ContextSourcesSummary }) {
  if (!s.used.length && !s.skipped.length) return null
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
      <span className="eyebrow" style={{ fontSize: 10 }}>
        Sources
      </span>
      {s.used.slice(0, 6).map((u, i) => (
        <span
          key={i}
          style={{ display: "inline-flex", alignItems: "center", gap: 5, height: 26, padding: "0 9px 0 4px", borderRadius: 13, border: "1px solid var(--bd)", background: "var(--s1)", fontSize: 12, color: "var(--t2)" }}
        >
          <span className="logo" style={{ width: 18, height: 18, fontSize: 8, borderRadius: 9 }}>
            {systemBadge(u.kind) || "·"}
          </span>
          {u.name}
        </span>
      ))}
      {s.skipped.length ? <span className="sub">Left out: {s.skipped.map((x) => `${x.label} (${x.count})`).join(", ")}</span> : null}
    </div>
  )
}

export function Ask() {
  const { api, nav, go, agents, prefs, setPrefs, toast, web, refresh } = useStore()
  const agent = useAgentName()
  const [convs, setConvs] = useState<Conversation[]>([])
  const [convsError, setConvsError] = useState<string | null>(null)
  const [q, setQ] = useState("")
  const [convId, setConvId] = useState<string | null>(nav.select ?? null)
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [loadingMsgs, setLoadingMsgs] = useState(false)
  const [draft, setDraft] = useState("")
  const [busy, setBusy] = useState(false)
  const [ctxOpen, setCtxOpen] = useState(true)
  const [voice, setVoice] = useState(false)
  const scroller = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLInputElement>(null)
  const sentInitial = useRef<string | null>(null)

  const loadConvs = useCallback(
    async (search = q) => {
      try {
        setConvs(await api.conversations(search))
        setConvsError(null)
      } catch (err) {
        setConvsError(err instanceof Error ? err.message : "Couldn't load conversations")
      }
    },
    [api, q],
  )

  useEffect(() => {
    const t = window.setTimeout(() => void loadConvs(q), q ? 250 : 0)
    return () => window.clearTimeout(t)
  }, [q, loadConvs])

  // Opening a stored conversation loads its history; a new one starts empty.
  const openConv = useCallback(
    async (id: string | null) => {
      setConvId(id)
      setVoice(false)
      if (!id) {
        setMsgs([])
        return
      }
      setLoadingMsgs(true)
      try {
        const rows = await api.messages(id)
        setMsgs(rows.map((m) => ({ id: m.id || mid(), role: m.role, text: m.content })))
      } catch (err) {
        toast(err instanceof Error ? err.message : "Couldn't load the conversation", "error")
      } finally {
        setLoadingMsgs(false)
      }
    },
    [api, toast],
  )

  useEffect(() => {
    if (nav.select) void openConv(nav.select)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nav.select])

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight })
  }, [msgs])

  const send = useCallback(
    async (text: string, opts: { fresh?: boolean } = {}) => {
      const t = text.trim()
      if (!t || busy) return
      setDraft("")
      setBusy(true)
      let id = opts.fresh ? null : convId
      const history = opts.fresh ? [] : msgs.filter((m) => !m.thinking && !m.error && m.text).map((m) => ({ role: m.role, text: m.text }))
      const botId = mid()
      setMsgs((prev) => [...(opts.fresh ? [] : prev), { id: mid(), role: "user", text: t }, { id: botId, role: "assistant", text: "", thinking: true }])
      const patch = (p: Partial<Msg>) => setMsgs((prev) => prev.map((m) => (m.id === botId ? { ...m, ...p } : m)))
      try {
        if (!id) {
          const conv = await api.createConversation(t)
          id = conv.id
          setConvId(conv.id)
          setConvs((prev) => [conv, ...prev.filter((c) => c.id !== conv.id)])
        }
        const result = await api.chat(
          { history, message: t, conversationId: id, agentId: prefs.agentId || null },
          {
            onText: (sofar) => patch({ text: sofar, thinking: false }),
            onStatus: (status) => patch({ status }),
          },
        )
        patch({ text: result.text || (result.pendingTask ? "" : "Done."), thinking: false, sources: result.sources, pending: result.pendingTask })
        if (result.pendingTask) void refresh("approvals")
        void loadConvs()
      } catch (err) {
        patch({ thinking: false, error: err instanceof Error ? err.message : "The answer didn't come through." })
      } finally {
        setBusy(false)
        input.current?.focus()
      }
    },
    [api, busy, convId, loadConvs, msgs, prefs.agentId, refresh],
  )

  // Asked from Home, the command bar or Quick Ask: start a new conversation with it.
  useEffect(() => {
    if (nav.ask && sentInitial.current !== nav.ask) {
      sentInitial.current = nav.ask
      void send(nav.ask, { fresh: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nav.ask])

  const pasteClipboard = async () => {
    try {
      const text = (await navigator.clipboard.readText()).trim()
      if (!text) return toast("The clipboard is empty.", "error")
      setDraft((d) => `${d ? `${d}\n\n` : ""}${text.slice(0, 4000)}`)
      input.current?.focus()
    } catch {
      toast("Gravitre couldn't read the clipboard.", "error")
    }
  }

  const conv = convs.find((c) => c.id === convId)
  const title = conv?.title || (convId ? "Conversation" : "New conversation")
  const lastSources = [...msgs].reverse().find((m) => m.sources)?.sources || null
  const lastText = [...msgs].reverse().find((m) => m.text && !m.thinking)?.text || ""

  return (
    <div className="split fade" style={{ height: "100%" }}>
      <section aria-label="Conversations" style={{ width: 300, flex: "none", borderRight: "1px solid var(--bd)", background: "var(--s1)", display: "flex", flexDirection: "column", minHeight: 0 }}>
        <div style={{ padding: "22px 16px 10px", display: "flex", flexDirection: "column", gap: 10 }}>
          <span className="eyebrow">Ask Gravitre</span>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.01em", flex: 1 }}>Conversations</span>
            <button className="btn btn-k btn-sm" onClick={() => void openConv(null)}>
              <Icon name="plus" size={14} />
              New
            </button>
          </div>
          <label htmlFor="conv-q" className="sr">
            Search conversations
          </label>
          <input
            id="conv-q"
            className="field"
            placeholder="Search conversations"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <div style={{ flex: 1, overflow: "auto", padding: "0 8px 12px", display: "flex", flexDirection: "column", gap: 2 }}>
          {convsError ? <div className="sub" style={{ padding: 10 }}>{convsError}</div> : null}
          {!convsError && convs.length === 0 ? (
            <div className="sub" style={{ padding: 10 }}>
              {q ? "No conversations match." : "Your conversations from the web, desktop and extension show up here."}
            </div>
          ) : null}
          {convs.map((c) => (
            <button key={c.id} className={`lr ${c.id === convId ? "on" : ""}`} onClick={() => void openConv(c.id)} style={{ padding: 10 }}>
              <span style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 1 }}>
                <span style={{ display: "flex", gap: 8 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", flex: 1 }}>{c.title}</span>
                  <span className="sub" style={{ fontSize: 11 }}>
                    {timeAgo(c.updatedAt)}
                  </span>
                </span>
                <span style={{ fontSize: 12, color: "var(--t3)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{c.preview || "No messages yet"}</span>
              </span>
            </button>
          ))}
        </div>
      </section>
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", minHeight: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "18px 24px 14px", borderBottom: "1px solid var(--bd)", background: "var(--s1)" }}>
          <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
            <span className="eyebrow">With {agent}</span>
            <span style={{ fontSize: 20, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{title}</span>
          </div>
          <button className="btn btn-sm" onClick={() => web(convId ? `/ai?c=${encodeURIComponent(convId)}` : "/ai")}>
            Continue on web ↗
          </button>
          <button className="ib" aria-label="Toggle context panel" aria-pressed={ctxOpen} onClick={() => setCtxOpen((o) => !o)}>
            <Icon name="panel" />
          </button>
        </div>
        {voice ? (
          <VoiceStage
            conversationId={convId}
            lastLine={lastText}
            onConversation={(id) => {
              setConvId(id)
              void loadConvs()
            }}
            onTurn={(turn) => setMsgs((prev) => [...prev, { id: mid(), role: turn.who === "you" ? "user" : "assistant", text: turn.text }])}
            onClose={() => setVoice(false)}
          />
        ) : (
          <>
            <div ref={scroller} aria-live="polite" style={{ flex: 1, minHeight: 0, overflow: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 18 }}>
              {loadingMsgs ? <span className="sub">Loading the conversation…</span> : null}
              {!loadingMsgs && msgs.length === 0 ? (
                <div style={{ margin: "auto", display: "flex", flexDirection: "column", alignItems: "center", gap: 10, textAlign: "center", maxWidth: 460 }}>
                  <Art src={ART.conversation} width={220} style={{ marginBottom: 8 }} />
                  <span className="eyebrow">New conversation</span>
                  <span style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.01em" }}>What should {agent} work on?</span>
                  <span className="sub" style={{ fontSize: 14 }}>
                    {agent} checks your connected apps, plans multi-step work, and asks before changing anything.
                  </span>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "center", marginTop: 6 }}>
                    {STARTERS.slice(0, 2).map((t) => (
                      <button key={t} className="qchip" style={{ height: 36, fontSize: 13 }} onClick={() => void send(t)}>
                        <span style={{ color: "var(--br)" }}>↳</span>
                        {t}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
              {msgs.map((m) =>
                m.role === "user" ? (
                  <div key={m.id} className="ubub" style={{ whiteSpace: "pre-wrap" }}>
                    {m.text}
                  </div>
                ) : (
                  <div key={m.id} style={{ display: "flex", gap: 12 }} className="fade">
                    <Avatar name={agent} />
                    <div style={{ display: "flex", flexDirection: "column", gap: 10, minWidth: 0, flex: 1, maxWidth: 680 }}>
                      <div style={{ fontSize: 13 }}>
                        <b>{agent}</b>
                      </div>
                      {m.thinking ? (
                        <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--sig)" }}>
                          <span className="typing">
                            <span />
                            <span />
                            <span />
                          </span>
                          {m.status || "Checking your sources"}
                        </span>
                      ) : null}
                      {m.text ? <RichText text={m.text} /> : null}
                      {m.error ? <ErrorLine message={m.error} /> : null}
                      {m.pending ? (
                        <div className="card" style={{ overflow: "hidden" }}>
                          <div className="band" style={{ padding: "12px 16px", display: "flex", gap: 10, alignItems: "center" }}>
                            <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
                              <span style={{ fontSize: 15, fontWeight: 600 }}>{m.pending.title}</span>
                              <span className="sub">Nothing changes until it's approved</span>
                            </div>
                            <span className="pill st-wait">
                              <span className="dot" />
                              Needs approval
                            </span>
                          </div>
                          {m.pending.steps.map((st, i) => (
                            <div key={i} style={{ display: "flex", gap: 10, alignItems: "center", minHeight: 42, padding: "0 16px", borderTop: "1px solid var(--bs)", fontSize: 13 }}>
                              <span className="stp st-q">
                                <Icon name="circle" size={12} strokeWidth={2} />
                              </span>
                              <span style={{ flex: 1 }}>{st}</span>
                            </div>
                          ))}
                          <div style={{ padding: "10px 16px", display: "flex", gap: 8, alignItems: "center", borderTop: "1px solid var(--bs)" }}>
                            <span className="sub" style={{ flex: 1 }}>
                              In Approvals · waiting on a decision
                            </span>
                            <button className="btn btn-l btn-sm" onClick={() => go("appr")}>
                              Review in Approvals →
                            </button>
                          </div>
                        </div>
                      ) : null}
                      {m.sources ? <Sources s={m.sources} /> : null}
                    </div>
                  </div>
                ),
              )}
            </div>
            <div style={{ padding: "12px 24px 20px" }}>
              <div className="composer">
                <label htmlFor="ask-in" className="sr">
                  Message {agent}
                </label>
                <input
                  id="ask-in"
                  ref={input}
                  className="ta"
                  autoFocus
                  placeholder={`Ask ${agent}`}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault()
                      void send(draft)
                    }
                  }}
                />
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <button className="ib" aria-label="Paste clipboard" title="Paste clipboard" style={{ width: 30, height: 30 }} onClick={() => void pasteClipboard()}>
                    <Icon name="clip" />
                  </button>
                  <label className="sr" htmlFor="agent-pick">
                    Agent
                  </label>
                  <select id="agent-pick" className="select-sm" value={prefs.agentId} onChange={(e) => setPrefs({ agentId: e.target.value })}>
                    <option value="">Gravitre</option>
                    {agents.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                        {a.role ? ` · ${a.role}` : ""}
                      </option>
                    ))}
                  </select>
                  <span style={{ flex: 1 }} />
                  <div className="mode" role="radiogroup" aria-label="Conversation mode">
                    <button className="on" role="radio" aria-checked="true">
                      <Icon name="ask" size={14} />
                      Text
                    </button>
                    <button role="radio" aria-checked="false" onClick={() => setVoice(true)}>
                      <Icon name="voice" size={14} />
                      Voice
                    </button>
                  </div>
                  <button className="btn btn-k btn-sm" disabled={busy || !draft.trim()} onClick={() => void send(draft)}>
                    Send <span style={{ opacity: 0.6 }}>↵</span>
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
      {ctxOpen ? (
        <aside aria-label="Context" style={{ width: 290, flex: "none", borderLeft: "1px solid var(--bd)", background: "var(--s1)", padding: "22px 18px", display: "flex", flexDirection: "column", gap: 22, overflow: "auto" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <span className="eyebrow">Sources used</span>
            {lastSources?.used.length ? (
              lastSources.used.map((s, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                  <Logo text={systemBadge(s.kind) || "·"} />
                  <span style={{ flex: 1, minWidth: 0 }}>{s.name}</span>
                  {s.freshness ? <span className="sub">{s.freshness}</span> : null}
                </div>
              ))
            ) : (
              <span className="sub">{lastSources?.summary || "Sources show here after an answer that used your connected data."}</span>
            )}
            {lastSources?.skipped.length ? (
              <>
                <span className="eyebrow" style={{ marginTop: 6 }}>
                  Left out
                </span>
                {lastSources.skipped.map((s, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--t3)" }}>
                    <span style={{ flex: 1 }}>
                      {s.label} ({s.count})
                    </span>
                  </div>
                ))}
              </>
            ) : null}
            <button className="btn btn-l btn-sm" style={{ alignSelf: "flex-start", padding: 0 }} onClick={() => web("/connectors")}>
              Connect apps on web ↗
            </button>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <span className="eyebrow">How context works</span>
            <span className="sub" style={{ fontSize: 13 }}>
              Answers use the apps and knowledge your workspace connected. Nothing is changed without an approval.
            </span>
            <button className="btn btn-l btn-sm" style={{ alignSelf: "flex-start", padding: 0 }} onClick={() => web("/ai/help/context")}>
              How Gravitre uses your context ↗
            </button>
          </div>
        </aside>
      ) : null}
    </div>
  )
}
