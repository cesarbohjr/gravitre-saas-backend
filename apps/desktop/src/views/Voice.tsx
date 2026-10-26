import { useEffect, useState } from "react"
import { useStore } from "../store"
import { AgentAvatar, ALT, Icon } from "../ui"
import { clock } from "../lib/model"
import { identityOf } from "../lib/identity"
import { useVoice, type VoiceState, type VoiceTurn } from "../components/useVoice"

function statusLine(state: VoiceState, agent: string, reason: string | null, muted: boolean): string {
  if (state === "checking") return "Checking voice…"
  if (state === "unavailable") return reason || "Voice isn't available here."
  if (muted) return "Microphone is muted."
  if (state === "listening") return "You're speaking…"
  if (state === "thinking") return `${agent} is thinking…`
  if (state === "speaking") return `${agent} is speaking…`
  return reason || "Tap the orb to talk"
}

function orbLabel(state: VoiceState): string {
  if (state === "listening") return "Listening. Click to send"
  if (state === "thinking") return "Thinking"
  if (state === "speaking") return "Speaking. Click to interrupt and talk"
  return "Click to start talking"
}

function orbClass(state: VoiceState, muted: boolean): string {
  if (state === "unavailable" || muted) return "orb off"
  if (state === "listening") return "orb listen"
  if (state === "speaking") return "orb speak"
  return "orb"
}

export function useAgentName(): string {
  const { agents, prefs } = useStore()
  return agents.find((a) => a.id === prefs.agentId)?.name || "Gravitre"
}

function AgentPill() {
  const { agents, prefs } = useStore()
  const name = useAgentName()
  const id = identityOf(agents, name, prefs.agentId || null)
  return (
    <span className="chip" style={{ height: 30, padding: "0 10px 0 6px" }}>
      <AgentAvatar id={id} size={18} />
      {name}
    </span>
  )
}

function Turns({ turns, state, agent }: { turns: VoiceTurn[]; state: VoiceState; agent: string }) {
  return (
    <div aria-live="polite" className="scroll" style={{ flex: 1, padding: "14px 16px", display: "flex", flexDirection: "column", gap: 14 }}>
      {turns.length === 0 && state !== "listening" ? <span className="sub">What you say and what {agent} answers shows up here.</span> : null}
      {turns.map((x, i) => (
        <div key={i} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <span className="sub" style={{ fontSize: 11 }}>
            {x.who === "you" ? "You" : agent} · {clock(x.at)}
          </span>
          <span style={{ fontSize: 13, lineHeight: 1.5 }}>{x.text}</span>
        </div>
      ))}
      {state === "listening" ? (
        <div className="card" style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 4, boxShadow: "none" }}>
          <span style={{ fontSize: 11, color: "var(--brk)", display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span className="dot" style={{ background: "var(--br)", width: 6, height: 6 }} />
            You · speaking
          </span>
          <span className="sub">Listening…</span>
        </div>
      ) : null}
    </div>
  )
}

/** The voice stage inside Ask: same voice loop, continuing the open conversation. */
export function VoiceStage({
  conversationId,
  onConversation,
  onTurn,
  onClose,
  lastLine,
}: {
  conversationId: string | null
  onConversation: (id: string) => void
  onTurn: (turn: VoiceTurn) => void
  onClose: () => void
  lastLine: string
}) {
  const { prefs } = useStore()
  const agent = useAgentName()
  const v = useVoice({ conversationId, agentId: prefs.agentId || null, onConversation, onTurn })
  const last = v.turns.length ? v.turns[v.turns.length - 1].text : lastLine
  const close = () => {
    v.end()
    onClose()
  }
  return (
    <div className="fade" style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", padding: "18px 24px 0" }}>
        <span role="status" aria-live="polite" style={{ fontSize: 18, color: "var(--t2)", flex: 1 }}>
          {statusLine(v.state, agent, v.reason, v.muted)}
        </span>
        <button aria-label="End voice" onClick={close} className="vbtn">
          <Icon name="x" size={18} />
        </button>
      </div>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 36 }}>
        <button
          className={orbClass(v.state, v.muted)}
          aria-label={orbLabel(v.state)}
          onClick={v.toggle}
          disabled={v.state === "unavailable" || v.state === "checking" || v.muted}
          style={{ width: 180, height: 180 }}
        />
        <button className="btn btn-q" onClick={close}>
          Tap to switch to text
        </button>
      </div>
      <div className="card" style={{ margin: "0 24px 20px", padding: "10px 14px", display: "flex", flexDirection: "column", gap: 2, boxShadow: "none" }}>
        <span className="sub" style={{ fontSize: 11 }}>
          Last in this conversation
        </span>
        <span style={{ fontSize: 13, lineHeight: 1.5 }}>{last || "Say anything to start."}</span>
      </div>
    </div>
  )
}

export function Voice() {
  const { nav, prefs, go } = useStore()
  const agent = useAgentName()
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [transcript, setTranscript] = useState(true)
  const v = useVoice({ conversationId, agentId: prefs.agentId || null, onConversation: setConversationId })

  // Opened by the push-to-talk shortcut: start listening straight away.
  useEffect(() => {
    if (nav.listen && v.state === "idle") void v.start()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nav.listen, v.state === "idle"])

  return (
    <div className="body fade" style={{ minHeight: 0 }}>
      <section className="dpane" aria-label="Voice" style={{ position: "relative" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "22px 24px 0 28px" }}>
          <span role="status" aria-live="polite" style={{ fontSize: 20, color: "var(--t2)", flex: 1 }}>
            {statusLine(v.state, agent, v.reason, v.muted)}
          </span>
          <AgentPill />
          <button
            aria-label="End voice conversation"
            onClick={() => {
              v.end()
              go("home")
            }}
            className="vbtn"
          >
            <Icon name="x" size={18} />
          </button>
          {!transcript ? (
            <button className="ib" aria-label="Show transcript" onClick={() => setTranscript(true)}>
              <Icon name="panel" />
            </button>
          ) : null}
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 40 }}>
          <button
            className={orbClass(v.state, v.muted)}
            aria-label={orbLabel(v.state)}
            onClick={v.toggle}
            disabled={v.state === "unavailable" || v.state === "checking" || v.muted}
            style={{ width: 240, height: 240 }}
          />
          <button
            className="btn btn-q btn-lg"
            style={{ fontSize: 16, color: "var(--t2)" }}
            onClick={() => {
              v.end()
              go({ view: "ask", select: conversationId })
            }}
          >
            Tap to switch to text
          </button>
        </div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 10, padding: "0 24px 22px" }}>
          <button
            aria-label={v.muted ? "Unmute microphone" : "Mute microphone"}
            aria-pressed={v.muted}
            onClick={v.toggleMute}
            className="vbtn"
            style={{ background: v.muted ? "var(--dgs)" : "var(--s1)", boxShadow: "0 0 0 1px var(--bd)", color: v.muted ? "var(--dgk)" : "var(--t1)" }}
          >
            <Icon name={v.muted ? "micoff" : "voice"} size={17} />
          </button>
          <span className="sub">
            Press <span className="kbd">{ALT} Space</span> to talk from any app
          </span>
        </div>
      </section>
      {transcript ? (
        <aside aria-label="Live transcript" style={{ width: 300, flex: "none", borderLeft: "1px solid var(--bd)", background: "var(--s1)", display: "flex", flexDirection: "column", minHeight: 0 }}>
          <div style={{ padding: "14px 12px 12px 16px", display: "flex", alignItems: "flex-start", gap: 8, borderBottom: "1px solid var(--bs)" }}>
            <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
              <span style={{ fontSize: 13, fontWeight: 600 }}>Transcript</span>
              <span className="sub" style={{ fontSize: 11 }}>
                Saved to this conversation in Ask
              </span>
            </div>
            <button className="ib" aria-label="Hide transcript" onClick={() => setTranscript(false)}>
              <Icon name="panel" />
            </button>
          </div>
          <Turns turns={v.turns} state={v.state} agent={agent} />
        </aside>
      ) : null}
    </div>
  )
}
