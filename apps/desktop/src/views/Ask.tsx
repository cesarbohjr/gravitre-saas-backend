import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { ART } from "../art"
import type { ContextSourcesSummary } from "@web/lib/context-sources"
import { policyLine } from "@web/components/approvals/decision-queue/model"
import { useStore } from "../store"
import { AgentAvatar, Art, ErrorLine, Icon, Logo, MOD, type IconName } from "../ui"
import { clock, dayLabel, systemBadge } from "../lib/model"
import { identityOf } from "../lib/identity"
import type { Conversation, PendingTask, Surface } from "../lib/api"
import { RichText } from "../components/RichText"
import { AgentChip, clipboardAttachment, Composer, withAttachments, type Attachment } from "../components/Composer"
import { STARTERS } from "./Home"
import { useAgentName, VoiceStage } from "./Voice"

type Msg = {
  id: string
  role: "user" | "assistant"
  text: string
  at?: string
  thinking?: boolean
  status?: string
  sources?: ContextSourcesSummary | null
  pending?: PendingTask | null
  error?: string
}

let seq = 0
const mid = () => `m${Date.now()}-${seq++}`

const SURFACE: Record<Surface, { label: string; icon: IconName; started: string }> = {
  web: { label: "Web", icon: "globe", started: "Started on the web" },
  desktop: { label: "Desktop", icon: "monitor", started: "Started on desktop" },
  extension: { label: "Extension", icon: "puzzle", started: "Started in the extension" },
  voice: { label: "Voice", icon: "voice", started: "Started by voice" },
}

function startedLine(c: Conversation | undefined): string {
  if (!c) return "New conversation"
  const where = c.surface ? SURFACE[c.surface].started : "Started"
  const d = dayLabel(c.createdAt)
  return `${where} · ${d === "Today" ? "today" : d === "Yesterday" ? "yesterday" : d} ${clock(c.createdAt)}`
}

export function Ask() {
  const { api, nav, go, agents, prefs, toast, web, refresh, approvals } = useStore()
  const agent = useAgentName()
  const agentId = identityOf(agents, agent, prefs.agentId || null)
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
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [attached, setAttached] = useState<(Attachment & { at: string })[]>([])
  const scroller = useRef<HTMLDivElement>(null)
  const search = useRef<HTMLInputElement>(null)
  const abort = useRef<AbortController | null>(null)
  const sentInitial = useRef<string | null>(null)

  const loadConvs = useCallback(
    async (term = q) => {
      try {
        setConvs(await api.conversations(term))
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

  // ⌘F searches conversations.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "f") {
        e.preventDefault()
        search.current?.focus()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  // Opening a stored conversation loads its history; a new one starts empty.
  const openConv = useCallback(
    async (id: string | null) => {
      abort.current?.abort()
      setConvId(id)
      setVoice(false)
      setAttached([])
      if (!id) {
        setMsgs([])
        return
      }
      setLoadingMsgs(true)
      try {
        const rows = await api.messages(id)
        setMsgs(rows.map((m) => ({ id: m.id || mid(), role: m.role, text: m.content, at: m.createdAt })))
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
      const files = opts.fresh ? [] : attachments
      const message = withAttachments(t, files)
      setDraft("")
      setAttachments([])
      if (files.length) setAttached((prev) => [...prev, ...files.map((f) => ({ ...f, at: new Date().toISOString() }))])
      setBusy(true)
      let id = opts.fresh ? null : convId
      const history = opts.fresh ? [] : msgs.filter((m) => !m.thinking && !m.error && m.text).map((m) => ({ role: m.role, text: m.text }))
      const botId = mid()
      const now = new Date().toISOString()
      setMsgs((prev) => [...(opts.fresh ? [] : prev), { id: mid(), role: "user", text: t, at: now }, { id: botId, role: "assistant", text: "", thinking: true, at: now }])
      const patch = (p: Partial<Msg>) => setMsgs((prev) => prev.map((m) => (m.id === botId ? { ...m, ...p } : m)))
      const ctl = new AbortController()
      abort.current = ctl
      try {
        if (!id) {
          const conv = await api.createConversation(t)
          id = conv.id
          setConvId(conv.id)
          setConvs((prev) => [conv, ...prev.filter((c) => c.id !== conv.id)])
        }
        const result = await api.chat(
          { history, message, conversationId: id, agentId: prefs.agentId || null },
          {
            onText: (sofar) => patch({ text: sofar, thinking: false }),
            onStatus: (status) => patch({ status }),
          },
          ctl.signal,
        )
        patch({ text: result.text || (result.pendingTask ? "" : "Done."), thinking: false, sources: result.sources, pending: result.pendingTask })
        if (result.pendingTask) void refresh("approvals")
        void loadConvs()
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          setMsgs((prev) => prev.map((m) => (m.id === botId ? { ...m, thinking: false, text: m.text || "Stopped." } : m)))
        } else {
          patch({ thinking: false, error: err instanceof Error ? err.message : "The answer didn't come through." })
        }
      } finally {
        if (abort.current === ctl) abort.current = null
        setBusy(false)
      }
    },
    [api, attachments, busy, convId, loadConvs, msgs, prefs.agentId, refresh],
  )

  // Asked from Home, the command bar or Quick Ask: start a new conversation with it.
  useEffect(() => {
    if (nav.ask && sentInitial.current !== nav.ask) {
      sentInitial.current = nav.ask
      void send(nav.ask, { fresh: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nav.ask])

  const attach = async () => {
    const a = await clipboardAttachment()
    if (a === "denied") toast("Gravitre couldn't read the clipboard.", "error")
    else if (!a) toast("The clipboard is empty.", "error")
    else setAttachments((prev) => [...prev, a])
  }

  const conv = convs.find((c) => c.id === convId)
  const title = conv?.title || (convId ? "Conversation" : "New conversation")
  const lastSources = [...msgs].reverse().find((m) => m.sources)?.sources || null
  const lastText = [...msgs].reverse().find((m) => m.text && !m.thinking)?.text || ""
  const related = convId ? approvals.data.filter((a) => a.context.conversationId === convId) : []

  const groups = useMemo(() => {
    const out: { label: string; items: Conversation[] }[] = []
    for (const c of convs) {
      const label = dayLabel(c.updatedAt)
      const last = out[out.length - 1]
      if (last && last.label === label) last.items.push(c)
      else out.push({ label, items: [c] })
    }
    return out
  }, [convs])

  return (
    <div className="body fade" style={{ minHeight: 0 }}>
      <section className="lpane" aria-label="Conversations" style={{ width: 268 }}>
        <div className="lhead">
          <h1>Ask</h1>
          <button className="ib" aria-label="New conversation" title="New conversation" onClick={() => void openConv(null)}>
            <Icon name="edit" />
          </button>
        </div>
        <div style={{ padding: "0 10px 6px" }}>
          <label className="field" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Icon name="search" size={14} style={{ color: "var(--t3)" }} />
            <input
              ref={search}
              aria-label="Search conversations"
              placeholder="Search conversations"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              style={{ flex: 1, minWidth: 0, border: 0, outline: 0, background: "transparent", color: "inherit", font: "inherit" }}
            />
            <span className="kbd">{MOD} F</span>
          </label>
        </div>
        <div className="scroll" style={{ flex: 1, padding: "0 6px 10px" }}>
          {convsError ? <div className="sub" style={{ padding: 10 }}>{convsError}</div> : null}
          {!convsError && convs.length === 0 ? (
            <div className="sub" style={{ padding: 10 }}>
              {q ? "No conversations match." : "Your conversations from the web, desktop and extension show up here."}
            </div>
          ) : null}
          {groups.map((g) => (
            <div key={g.label}>
              <div className="grp">{g.label}</div>
              {g.items.map((c) => (
                <button key={c.id} className={`cv ${c.id === convId ? "on" : ""}`} aria-current={c.id === convId ? "true" : undefined} onClick={() => void openConv(c.id)}>
                  <AgentAvatar id={agentId} size={20} />
                  <span style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 1 }}>
                    <span className="ell" style={{ fontSize: 13, fontWeight: 600 }}>
                      {c.title}
                    </span>
                    <span className="sub ell">{c.preview || "No messages yet"}</span>
                    {c.surface ? (
                      <span className="sub" style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11 }}>
                        <Icon name={SURFACE[c.surface].icon} size={11} />
                        {SURFACE[c.surface].label}
                      </span>
                    ) : null}
                  </span>
                </button>
              ))}
            </div>
          ))}
        </div>
      </section>
      <section className="dpane" aria-label="Conversation">
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 16px 10px 24px", borderBottom: "1px solid var(--bs)" }}>
          <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
            <span className="ell" style={{ fontSize: 15, fontWeight: 600 }}>
              {title}
            </span>
            <span className="sub">{startedLine(conv)}</span>
          </div>
          <span className="chip">
            <AgentAvatar id={agentId} size={18} />
            {agent}
          </span>
          <button className="mlink" onClick={() => web(convId ? `/ai?c=${encodeURIComponent(convId)}` : "/ai")}>
            Continue on web ↗
          </button>
          <button className="ib" aria-label={ctxOpen ? "Hide context" : "Show context"} aria-pressed={ctxOpen} onClick={() => setCtxOpen((o) => !o)}>
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
            onTurn={(turn) => setMsgs((prev) => [...prev, { id: mid(), role: turn.who === "you" ? "user" : "assistant", text: turn.text, at: turn.at }])}
            onClose={() => setVoice(false)}
          />
        ) : (
          <>
            <div ref={scroller} aria-live="polite" className="scroll" style={{ flex: 1, padding: "18px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
              {loadingMsgs ? <span className="sub">Loading the conversation…</span> : null}
              {!loadingMsgs && msgs.length === 0 ? (
                <div style={{ margin: "auto", display: "flex", flexDirection: "column", alignItems: "center", gap: 8, textAlign: "center", maxWidth: 420 }}>
                  <Art src={ART.conversation} width={180} style={{ marginBottom: 6 }} />
                  <span style={{ fontSize: 20, fontWeight: 600 }}>What should {agent} work on?</span>
                  <span className="sub" style={{ fontSize: 13 }}>
                    {agent} checks your connected apps, plans multi-step work, and asks before changing anything.
                  </span>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "center", marginTop: 6 }}>
                    {STARTERS.slice(0, 3).map((t) => (
                      <button key={t} className="btn btn-sm" style={{ borderRadius: 14 }} onClick={() => void send(t)}>
                        {t}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
              {msgs.map((m) =>
                m.role === "user" ? (
                  <div key={m.id} className="ubub">
                    {m.text}
                  </div>
                ) : (
                  <div key={m.id} style={{ display: "flex", gap: 10 }} className="fade">
                    <AgentAvatar id={agentId} size={22} />
                    <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 0, flex: 1, maxWidth: 640 }}>
                      <div style={{ fontSize: 13, display: "flex", gap: 6, alignItems: "center" }}>
                        <b style={{ fontWeight: 600 }}>{agent}</b>
                        {m.thinking || (busy && m === msgs[msgs.length - 1]) ? (
                          <span style={{ color: "var(--sig)", display: "inline-flex", alignItems: "center", gap: 5 }}>
                            <span className="dot" style={{ background: "var(--sig)", width: 5, height: 5 }} />
                            {m.thinking ? m.status || "Checking your sources" : "Writing"}
                          </span>
                        ) : (
                          <span className="sub">
                            {agentId.dept.label}
                            {m.at ? ` · ${clock(m.at)}` : ""}
                          </span>
                        )}
                      </div>
                      {m.thinking ? (
                        <span className="typing" aria-label="Thinking">
                          <span />
                          <span />
                          <span />
                        </span>
                      ) : null}
                      {m.text ? <RichText text={m.text} /> : null}
                      {m.error ? <ErrorLine message={m.error} /> : null}
                      {m.pending ? (
                        <div className="card" style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", boxShadow: "none" }}>
                          <Logo text="·" style={{ width: 28, height: 28 }} />
                          <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
                            <span className="ell" style={{ fontSize: 13, fontWeight: 600 }}>
                              {m.pending.title}
                            </span>
                            <span className="sub ell">
                              {m.pending.steps.length ? `${m.pending.steps.length} ${m.pending.steps.length === 1 ? "step" : "steps"} · ` : ""}
                              Nothing changes until it's approved
                            </span>
                          </div>
                          <span className="pill st-wait">
                            <span className="dot" />
                            Needs approval
                          </span>
                          <button className="btn btn-sm" onClick={() => go("appr")}>
                            Review
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </div>
                ),
              )}
            </div>
            <div style={{ padding: "8px 24px 18px" }}>
              <Composer
                id="ask-in"
                autoFocus
                value={draft}
                onChange={setDraft}
                onSend={() => void send(draft)}
                placeholder={busy ? `Type to redirect ${agent}, or press Esc to stop` : `Ask ${agent}`}
                busy={busy}
                onStop={() => abort.current?.abort()}
                onVoice={() => setVoice(true)}
                attachments={attachments}
                onAttach={() => void attach()}
                onRemove={(id) => setAttachments((prev) => prev.filter((a) => a.id !== id))}
                leading={<AgentChip />}
              />
            </div>
          </>
        )}
      </section>
      {ctxOpen ? (
        <aside aria-label="Context" className="ctx">
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>Sources used</h3>
            {lastSources?.used.length ? (
              lastSources.used.map((s, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                  <Logo text={systemBadge(s.kind) || "·"} />
                  <span className="ell" style={{ flex: 1, minWidth: 0 }}>
                    {s.name}
                  </span>
                  {s.freshness ? <span className="sub">{s.freshness}</span> : null}
                </div>
              ))
            ) : (
              <span className="sub">{lastSources?.summary || "Sources show here after an answer that used your connected data."}</span>
            )}
            {lastSources?.skipped.map((s, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--t3)" }}>
                <Logo text={systemBadge(s.label) || "·"} />
                <span style={{ flex: 1 }}>
                  Left out: {s.label} ({s.count})
                </span>
              </div>
            ))}
            {lastSources?.skipped.length ? (
              <button className="link" style={{ alignSelf: "flex-start" }} onClick={() => web("/connectors")}>
                Connect apps on web ↗
              </button>
            ) : null}
          </div>
          {attached.length ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>Attached</h3>
              {attached.map((a) => (
                <div key={a.id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                  <Icon name={a.icon} size={14} style={{ color: "var(--t3)" }} />
                  <span className="ell" style={{ flex: 1 }}>
                    {a.label}
                  </span>
                  <span className="sub">{clock(a.at)}</span>
                </div>
              ))}
            </div>
          ) : null}
          {related.length ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>Waiting on approval</h3>
              {related.map((a) => (
                <div key={a.id} className="card" style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 6, boxShadow: "none" }}>
                  <span className="pill st-wait" style={{ alignSelf: "flex-start" }}>
                    <span className="dot" />
                    Needs approval
                  </span>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{a.title}</span>
                  <span className="sub">{policyLine(a)}</span>
                  <button className="link" style={{ alignSelf: "flex-start" }} onClick={() => go({ view: "appr", select: a.id })}>
                    Review
                  </button>
                </div>
              ))}
            </div>
          ) : null}
          <button className="link" style={{ alignSelf: "flex-start", marginTop: "auto" }} onClick={() => web("/ai/help/context")}>
            How Gravitre uses your context ↗
          </button>
        </aside>
      ) : null}
    </div>
  )
}
