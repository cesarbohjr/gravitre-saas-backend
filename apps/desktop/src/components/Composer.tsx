import { useRef, type ReactNode } from "react"
import { useStore } from "../store"
import { identityOf } from "../lib/identity"
import { AgentAvatar, Icon } from "../ui"

/** The agent chip: who answers. Gravitre (no agent) routes to the right one. */
export function AgentChip() {
  const { agents, prefs, setPrefs } = useStore()
  const id = identityOf(agents, null, prefs.agentId || null)
  return (
    <span className="chip" style={{ position: "relative", paddingRight: 8 }}>
      <AgentAvatar id={id} size={18} />
      <span>{id.name}</span>
      <label className="sr" htmlFor="agent-pick">
        Agent
      </label>
      <select
        id="agent-pick"
        value={prefs.agentId}
        onChange={(e) => setPrefs({ agentId: e.target.value })}
        style={{ position: "absolute", inset: 0, opacity: 0, cursor: "pointer" }}
      >
        <option value="">Gravitre</option>
        {agents.map((a) => (
          <option key={a.id} value={a.id}>
            {a.name}
            {a.department || a.role ? ` · ${a.department || a.role}` : ""}
          </option>
        ))}
      </select>
    </span>
  )
}

export function ModeSwitch({ onVoice }: { onVoice: () => void }) {
  return (
    <div className="mode" role="radiogroup" aria-label="Conversation mode">
      <button className="on" role="radio" aria-checked="true">
        <Icon name="ask" size={14} />
        Text
      </button>
      <button role="radio" aria-checked="false" onClick={onVoice}>
        <Icon name="voice" size={14} />
        Voice
      </button>
    </div>
  )
}

export type Attachment = { id: string; label: string; text: string; icon: "clip" | "globe" }

/** Reads the clipboard as an attachment ("Clipboard · 6 lines"); null when it is empty or unreadable. */
export async function clipboardAttachment(): Promise<Attachment | null | "denied"> {
  try {
    const text = (await navigator.clipboard.readText()).trim()
    if (!text) return null
    const lines = text.split(/\r?\n/).filter((l) => l.trim()).length
    return { id: `clip-${Date.now()}`, label: `Clipboard · ${lines} ${lines === 1 ? "line" : "lines"}`, text: text.slice(0, 8000), icon: "clip" }
  } catch {
    return "denied"
  }
}

/** The message sent to the assistant: what was typed, then each attachment as quoted context. */
export function withAttachments(text: string, attachments: Attachment[]): string {
  if (!attachments.length) return text
  const blocks = attachments.map((a) => `${a.label}:\n"""\n${a.text}\n"""`)
  return `${text}\n\n${blocks.join("\n\n")}`
}

export function Composer({
  value,
  onChange,
  onSend,
  placeholder,
  busy,
  onStop,
  onVoice,
  attachments = [],
  onAttach,
  onRemove,
  leading,
  autoFocus,
  id = "composer",
  minRows = 1,
}: {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  placeholder: string
  busy?: boolean
  onStop?: () => void
  onVoice: () => void
  attachments?: Attachment[]
  onAttach?: () => void
  onRemove?: (id: string) => void
  leading?: ReactNode
  autoFocus?: boolean
  id?: string
  minRows?: number
}) {
  const ref = useRef<HTMLTextAreaElement>(null)
  return (
    <div className="composer" onClick={() => ref.current?.focus()}>
      {attachments.length ? (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {attachments.map((a) => (
            <span key={a.id} className="attach">
              <Icon name={a.icon} size={13} style={{ color: "var(--t3)" }} />
              {a.label}
              {onRemove ? (
                <button className="ib" aria-label={`Remove ${a.label}`} style={{ width: 18, height: 18, borderRadius: 5 }} onClick={() => onRemove(a.id)}>
                  <Icon name="x" size={12} />
                </button>
              ) : null}
            </span>
          ))}
        </div>
      ) : null}
      <label htmlFor={id} className="sr">
        {placeholder}
      </label>
      <textarea
        id={id}
        ref={ref}
        className="ta"
        rows={minRows}
        autoFocus={autoFocus}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault()
            if (!busy) onSend()
          }
          if (e.key === "Escape" && busy && onStop) {
            e.preventDefault()
            onStop()
          }
        }}
        style={{ minHeight: minRows * 22 }}
      />
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        {leading}
        {onAttach ? (
          <button className="ib" aria-label="Attach clipboard" title="Attach clipboard" style={{ width: 28, height: 28 }} onClick={onAttach}>
            <Icon name="clip" />
          </button>
        ) : null}
        <span style={{ flex: 1 }} />
        <ModeSwitch onVoice={onVoice} />
        {busy && onStop ? (
          <button className="btn btn-sm" onClick={onStop}>
            <Icon name="stop" size={12} style={{ fill: "currentColor" }} />
            Stop
          </button>
        ) : (
          <button className="ib send" aria-label="Send" disabled={busy || !value.trim()} onClick={onSend}>
            <Icon name="up" size={15} strokeWidth={2} />
          </button>
        )}
      </div>
    </div>
  )
}
