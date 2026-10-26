"use client"

import { useEffect, useRef, useState, type ReactNode } from "react"
import { usePathname } from "next/navigation"
import { Bell, Check, CircleAlert, Info, Loader2, ShieldAlert, X } from "lucide-react"
import { registerAgentsToaster, removeToast, type AgentsToast, type ToastTone } from "./toast"

const ICONS: Record<ToastTone, ReactNode> = {
  success: <Check size={18} strokeWidth={2.2} aria-hidden />,
  error: <CircleAlert size={18} strokeWidth={2.2} aria-hidden />,
  warning: <ShieldAlert size={18} strokeWidth={2.2} aria-hidden />,
  info: <Info size={18} strokeWidth={2.2} aria-hidden />,
  message: <Bell size={18} strokeWidth={2.2} aria-hidden />,
  loading: <Loader2 size={18} strokeWidth={2.2} className="ag-spin" aria-hidden />,
}

const SECTION_LABELS: Record<string, string> = {
  ai: "Ask Gravitre",
  approvals: "Approvals",
  "trust-safety": "Trust and safety",
  runs: "Runs",
  plays: "Plays",
  connectors: "Connectors",
  marketplace: "Marketplace",
  intelligence: "Intelligence",
}

/** The page a toast came from, as the design's mono eyebrow ("SOURCES", "APPROVALS"). */
export function eyebrowForPath(pathname: string | null): string {
  const segment = (pathname ?? "").split("/").filter(Boolean)[0] ?? "home"
  const label = SECTION_LABELS[segment] ?? segment.replace(/[-_]+/g, " ")
  return label.toUpperCase()
}

function ToastCard({ item, fallbackEyebrow, paused }: { item: AgentsToast; fallbackEyebrow: string; paused: boolean }) {
  const timed = Number.isFinite(item.duration) && item.duration > 0
  const remaining = useRef(item.duration)
  const startedAt = useRef(Date.now())

  // Restart the clock whenever the toast is replaced in place (same id, new content).
  useEffect(() => {
    remaining.current = item.duration
    startedAt.current = Date.now()
  }, [item.createdAt, item.duration])

  useEffect(() => {
    // The cleanup banks the time already shown, so pausing and resuming carries on where it stopped.
    if (!timed || paused) return
    startedAt.current = Date.now()
    const timer = window.setTimeout(() => removeToast(item.id, "auto"), remaining.current)
    return () => {
      window.clearTimeout(timer)
      remaining.current = Math.max(0, remaining.current - (Date.now() - startedAt.current))
    }
  }, [paused, timed, item.id, item.createdAt])

  const act = (handler: (event: React.MouseEvent<HTMLButtonElement>) => void) => (event: React.MouseEvent<HTMLButtonElement>) => {
    handler(event)
    if (!event.defaultPrevented) removeToast(item.id)
  }

  return (
    <div role={item.tone === "error" ? "alert" : "status"} className="ag-toast" data-tone={item.tone}>
      <div className="ag-toast-body">
        <span className="ag-tile">{ICONS[item.tone]}</span>
        <div className="ag-toast-copy">
          <span className="ag-eyebrow">{item.eyebrow ?? fallbackEyebrow}</span>
          <span className="ag-toast-title">{item.title}</span>
          {item.description ? <span className="ag-toast-desc">{item.description}</span> : null}
          {item.action || item.cancel ? (
            <div className="ag-toast-actions">
              {item.action ? (
                <button type="button" className={`ag-btn sm ${item.tone === "error" ? "dark" : "primary"}`} onClick={act(item.action.onClick)}>
                  {item.action.label}
                </button>
              ) : null}
              {item.cancel ? (
                <button type="button" className="ag-btn sm ghost" onClick={act(item.cancel.onClick)}>
                  {item.cancel.label}
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
        <button type="button" aria-label="Dismiss" className="ag-x" onClick={() => removeToast(item.id)}>
          <X size={14} strokeWidth={2.4} aria-hidden />
        </button>
      </div>
      {timed ? (
        <div className="ag-toast-track" aria-hidden>
          <div
            key={item.createdAt}
            className="ag-toast-bar"
            style={{ animationDuration: `${item.duration}ms`, animationPlayState: paused ? "paused" : "running" }}
          />
        </div>
      ) : null}
    </div>
  )
}

/** Bottom-left stack of up to three toasts (full width on phones). Hover or focus pauses the clocks. */
export function AgentsToaster() {
  const [items, setItems] = useState<AgentsToast[]>([])
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const pathname = usePathname()

  useEffect(() => registerAgentsToaster(setItems), [])

  const paused = hovered || focused
  return (
    <section
      className="ag-toasts"
      aria-label="Notifications"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFocused(false)
      }}
    >
      {items.map((item) => (
        <ToastCard key={item.id} item={item} fallbackEyebrow={eyebrowForPath(pathname)} paused={paused} />
      ))}
    </section>
  )
}
