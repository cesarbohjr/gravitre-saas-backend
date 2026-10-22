import { useEffect, useState } from "react"
import { useStore } from "../store"
import { ALT, Avatar, Icon } from "../ui"
import { clock } from "../lib/model"
import { useVoice, type VoiceState, type VoiceTurn } from "../components/useVoice"

function statusLine(state: VoiceState, agent: string, reason: string | null, muted: boolean): string {
  if (state === "checking") return "Checking voice…"
  if (state === "unavailable") return reason || "Voice isn't available here."
  if (muted) return "Microphone is muted."
  if (state === "listening") return "You're speaking… tap the orb to send"
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

export function useAgentName(): string {
  const { agents, prefs } = useStore()
  return agents.find((a) => a.id === prefs.agentId)?.name || "Gravitre"
}

/** The dark voice stage inside Ask: same voice loop, continuing the open conversation. */
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
  return (
    <div className="vstage fade" style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", position: "relative", overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", padding: "22px 24px 0 32px" }}>
        <span role="status" aria-live="polite" style={{ fontSize: 20, color: "#a7abb1", flex: 1 }}>
          {statusLine(v.state, agent, v.reason, v.muted)}
        </span>
        <button
          aria-label="End voice"
          onClick={() => {
            v.end()
            onClose()
          }}
          className="vbtn"
          style={{ width: 44, height: 44 }}
        >
          <Icon name="x" size={20} />
        </button>
      </div>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 40 }}>
        <button
          className={`orb ${v.state === "listening" ? "listen" : ""} ${v.state === "unavailable" || v.muted ? "off" : ""}`}
          aria-label={orbLabel(v.state)}
          onClick={v.toggle}
          disabled={v.state === "unavailable" || v.state === "checking" || v.muted}
          style={{ width: 220, height: 220, minWidth: 220, minHeight: 220 }}
        />
        <button
          onClick={() => {
            v.end()
            onClose()
          }}
          style={{ border: 0, background: "transparent", color: "#b9bfc4", fontSize: 18, cursor: "pointer", padding: "8px 12px", borderRadius: 10 }}
        >
          Tap to switch to text
        </button>
      </div>
      <div style={{ margin: "0 24px 24px", padding: "12px 16px", borderRadius: 14, background: "#1d2024", border: "1px solid #2b2f34", display: "flex", flexDirection: "column", gap: 4 }}>
        <span className="mono" style={{ fontSize: 10, letterSpacing: ".14em", textTransform: "uppercase", color: "#8a8f95" }}>
          Last in this conversation
        </span>
        <span style={{ fontSize: 14, color: "#e9eaec", lineHeight: 1.5 }}>{last || "Say anything to start."}</span>
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
    <div className="vstage" style={{ display: "flex", height: "100%", minHeight: 0 }}>
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "28px 28px 0 40px" }}>
          <span role="status" aria-live="polite" style={{ fontSize: 22, color: "#a7abb1", flex: 1 }}>
            {statusLine(v.state, agent, v.reason, v.muted)}
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6, height: 32, padding: "0 12px 0 4px", borderRadius: 16, background: "#1d2024", fontSize: 13, fontWeight: 500, color: "#e9eaec" }}>
            <Avatar name={agent} size={24} />
            {agent}
          </span>
          <button
            aria-label="End voice conversation"
            onClick={() => {
              v.end()
              go("home")
            }}
            className="vbtn"
            style={{ width: 48, height: 48 }}
          >
            <Icon name="x" size={22} />
          </button>
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 48 }}>
          <button
            className={`orb ${v.state === "listening" ? "listen" : ""} ${v.state === "unavailable" || v.muted ? "off" : ""}`}
            aria-label={orbLabel(v.state)}
            onClick={v.toggle}
            disabled={v.state === "unavailable" || v.state === "checking" || v.muted}
            style={{ width: 280, height: 280, minWidth: 280, minHeight: 280 }}
          />
          <button
            onClick={() => {
              v.end()
              go({ view: "ask", select: conversationId })
            }}
            style={{ border: 0, background: "transparent", color: "#b9bfc4", fontSize: 20, cursor: "pointer", padding: "8px 12px", borderRadius: 10 }}
          >
            Tap to switch to text
          </button>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "0 28px 26px 40px" }}>
          <button
            aria-label={v.muted ? "Unmute microphone" : "Mute microphone"}
            aria-pressed={v.muted}
            onClick={v.toggleMute}
            className="vbtn"
            style={{ width: 48, height: 48, border: "1px solid #353a3f", background: v.muted ? "#3a2023" : "transparent" }}
          >
            <Icon name={v.muted ? "micoff" : "voice"} size={20} />
          </button>
          <span style={{ flex: 1, fontSize: 13, color: "#8a8f95" }}>
            Press{" "}
            <span className="kbd" style={{ background: "#1d2024", borderColor: "#353a3f", color: "#cbd1d6" }}>
              {ALT} Space
            </span>{" "}
            from any app to start talking, and again to send.
          </span>
          <button
            onClick={() => setTranscript((t) => !t)}
            style={{ height: 32, padding: "0 12px", borderRadius: 9, border: "1px solid #353a3f", background: "transparent", color: "#e9eaec", fontSize: 12, cursor: "pointer" }}
          >
            {transcript ? "Hide transcript" : "Show transcript"}
          </button>
        </div>
      </div>
      {transcript ? (
        <aside aria-label="Live transcript" style={{ width: 340, flex: "none", borderLeft: "1px solid #2b2f34", background: "#16181b", display: "flex", flexDirection: "column" }}>
          <div style={{ padding: "26px 20px 14px", display: "flex", flexDirection: "column", gap: 4, borderBottom: "1px solid #2b2f34" }}>
            <span className="mono" style={{ fontSize: 11, letterSpacing: ".14em", textTransform: "uppercase", color: "#8a8f95" }}>
              Transcript
            </span>
            <span style={{ fontSize: 13, color: "#a7abb1" }}>Saved to the conversation in Ask</span>
          </div>
          <div aria-live="polite" style={{ flex: 1, overflow: "auto", padding: "18px 20px", display: "flex", flexDirection: "column", gap: 16 }}>
            {v.turns.length === 0 ? <span style={{ fontSize: 13, color: "#8a8f95" }}>What you say and what {agent} answers shows up here.</span> : null}
            {v.turns.map((x, i) => (
              <div key={i} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span className="mono" style={{ fontSize: 10, letterSpacing: ".1em", textTransform: "uppercase", color: "#8a8f95" }}>
                  {x.who === "you" ? "You" : agent} · {clock(x.at)}
                </span>
                <span style={{ fontSize: 14, lineHeight: 1.55, color: "#e9eaec" }}>{x.text}</span>
              </div>
            ))}
            {v.state === "listening" ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span className="mono" style={{ fontSize: 10, letterSpacing: ".1em", textTransform: "uppercase", color: "#8a8f95" }}>
                  You · speaking
                </span>
                <span style={{ fontSize: 14, color: "#8a8f95" }}>Listening…</span>
              </div>
            ) : null}
          </div>
        </aside>
      ) : null}
    </div>
  )
}
