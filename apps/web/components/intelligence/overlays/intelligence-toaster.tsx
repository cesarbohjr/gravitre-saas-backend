"use client"

import { useEffect, useRef, useState, type ReactNode } from "react"
import { usePathname } from "next/navigation"
import { Bell, Check, CircleAlert, Download, Info, Loader2, Shield, ShieldAlert, X } from "lucide-react"
import {
  registerIntelligenceToaster,
  removeIntelligenceToast,
  type IntelligenceToast,
  type IntelligenceToastTone,
} from "./toast"

const ICONS: Record<IntelligenceToastTone, ReactNode> = {
  success: <Check size={18} strokeWidth={2.2} aria-hidden />,
  error: <CircleAlert size={18} strokeWidth={2.2} aria-hidden />,
  warning: <ShieldAlert size={18} strokeWidth={2.2} aria-hidden />,
  approval: <Shield size={18} strokeWidth={2.2} aria-hidden />,
  info: <Info size={18} strokeWidth={2.2} aria-hidden />,
  message: <Bell size={18} strokeWidth={2.2} aria-hidden />,
  loading: <Loader2 size={18} strokeWidth={2.2} className="ig-spin" aria-hidden />,
  progress: <Download size={18} strokeWidth={2.2} aria-hidden />,
}

/** Primary action colour per tone: dark for failures (Reconnect), green otherwise. */
const ACTION_CLASS: Partial<Record<IntelligenceToastTone, string>> = { error: "dark" }

const PAGE_LABELS: Array<[RegExp, string]> = [
  [/^\/intelligence\/learning/, "Knowledge"],
  [/^\/intelligence\/predictive/, "Forecasts"],
  [/^\/intelligence\/accounts/, "Accounts"],
  [/^\/intelligence\/performance/, "Impact"],
  [/^\/intelligence\/reports/, "Reports"],
  [/^\/intelligence\/data/, "Data"],
  [/^\/intelligence\/model/, "Models"],
  [/^\/models/, "Models"],
]

/** The Intelligence page a toast came from, as the design's mono eyebrow. */
export function intelligenceEyebrowForPath(pathname: string | null): string {
  const path = pathname ?? ""
  const match = PAGE_LABELS.find(([pattern]) => pattern.test(path))
  return (match ? match[1] : "Intelligence").toUpperCase()
}

function ToastCard({
  item,
  fallbackEyebrow,
  paused,
}: {
  item: IntelligenceToast
  fallbackEyebrow: string
  paused: boolean
}) {
  const timed = Number.isFinite(item.duration) && item.duration > 0
  const remaining = useRef(item.duration)
  const startedAt = useRef(Date.now())

  useEffect(() => {
    remaining.current = item.duration
    startedAt.current = Date.now()
  }, [item.createdAt, item.duration])

  useEffect(() => {
    // The cleanup banks the time already shown, so pausing and resuming carries on where it stopped.
    if (!timed || paused) return
    startedAt.current = Date.now()
    const timer = window.setTimeout(() => removeIntelligenceToast(item.id, "auto"), remaining.current)
    return () => {
      window.clearTimeout(timer)
      remaining.current = Math.max(0, remaining.current - (Date.now() - startedAt.current))
    }
  }, [paused, timed, item.id, item.createdAt])

  const act =
    (handler: (event: React.MouseEvent<HTMLButtonElement>) => void) =>
    (event: React.MouseEvent<HTMLButtonElement>) => {
      handler(event)
      if (!event.defaultPrevented) removeIntelligenceToast(item.id)
    }

  const progress = item.tone === "progress" ? Math.max(0, Math.min(1, item.progress ?? 0)) : null

  return (
    <div role={item.tone === "error" ? "alert" : "status"} className="ig-toast" data-tone={item.tone}>
      <div className="ig-toast-body">
        <span className="ig-tile">{ICONS[item.tone]}</span>
        <div className="ig-toast-copy">
          <span className="ig-eyebrow">{item.eyebrow ?? fallbackEyebrow}</span>
          <span className="ig-toast-title">{item.title}</span>
          {item.description ? <span className="ig-toast-desc">{item.description}</span> : null}
          {item.action || item.cancel ? (
            <div className="ig-toast-actions">
              {item.action ? (
                <button
                  type="button"
                  className={`ig-btn sm ${ACTION_CLASS[item.tone] ?? "primary"}`}
                  onClick={act(item.action.onClick)}
                >
                  {item.action.label}
                </button>
              ) : null}
              {item.cancel ? (
                <button type="button" className="ig-btn sm ghost" onClick={act(item.cancel.onClick)}>
                  {item.cancel.label}
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
        <button type="button" aria-label="Dismiss" className="ig-x" onClick={() => removeIntelligenceToast(item.id)}>
          <X size={14} strokeWidth={2.4} aria-hidden />
        </button>
      </div>
      {progress != null ? (
        <div
          className="ig-toast-track"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progress * 100)}
        >
          <div className="ig-toast-fill" style={{ width: `${progress * 100}%` }} />
        </div>
      ) : timed ? (
        <div className="ig-toast-track" aria-hidden>
          <div
            key={item.createdAt}
            className="ig-toast-bar"
            style={{ animationDuration: `${item.duration}ms`, animationPlayState: paused ? "paused" : "running" }}
          />
        </div>
      ) : null}
    </div>
  )
}

/** Bottom-left stack of up to three toasts (full width on phones). Hover or focus pauses the clocks. */
export function IntelligenceToaster() {
  const [items, setItems] = useState<IntelligenceToast[]>([])
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const pathname = usePathname()

  useEffect(() => registerIntelligenceToaster(setItems), [])

  const paused = hovered || focused
  return (
    <section
      className="ig-toasts"
      aria-label="Intelligence notifications"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFocused(false)
      }}
    >
      {items.map((item) => (
        <ToastCard key={item.id} item={item} fallbackEyebrow={intelligenceEyebrowForPath(pathname)} paused={paused} />
      ))}
    </section>
  )
}
