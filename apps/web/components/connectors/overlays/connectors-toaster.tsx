"use client"

import { useEffect, useRef, useState, type ReactNode } from "react"
import { Bell, Check, CircleAlert, Info, Loader2, TriangleAlert, X } from "lucide-react"
import { vendorLook } from "@/components/connectors/redesign/vendor-look"
import { registerConnectorsToaster, removeConnectorsToast, type ConnectorsToast, type ConnectorsToastTone } from "./toast"

const ICONS: Record<ConnectorsToastTone, ReactNode> = {
  success: <Check size={18} strokeWidth={2.2} aria-hidden />,
  error: <CircleAlert size={18} strokeWidth={2.2} aria-hidden />,
  warning: <TriangleAlert size={18} strokeWidth={2.2} aria-hidden />,
  info: <Info size={18} strokeWidth={2.2} aria-hidden />,
  message: <Bell size={18} strokeWidth={2.2} aria-hidden />,
  loading: <Loader2 size={18} strokeWidth={2.2} className="cno-spin" aria-hidden />,
}

const TOPIC: Record<ConnectorsToastTone, string> = {
  success: "Done",
  error: "Error",
  warning: "Needs attention",
  info: "Update",
  message: "Connectors",
  loading: "Working",
}

/** Failures ask for a dark "Reconnect" / "Try again"; everything else is green, as drawn. */
const ACTION_CLASS: Partial<Record<ConnectorsToastTone, string>> = { error: "dark", loading: "ghost" }

function ToastCard({ item, paused }: { item: ConnectorsToast; paused: boolean }) {
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
    const timer = window.setTimeout(() => removeConnectorsToast(item.id, "auto"), remaining.current)
    return () => {
      window.clearTimeout(timer)
      remaining.current = Math.max(0, remaining.current - (Date.now() - startedAt.current))
    }
  }, [paused, timed, item.id, item.createdAt])

  const act =
    (handler: (event: React.MouseEvent<HTMLButtonElement>) => void) =>
    (event: React.MouseEvent<HTMLButtonElement>) => {
      handler(event)
      if (!event.defaultPrevented) removeConnectorsToast(item.id)
    }

  const look = item.vendor ? vendorLook(item.vendor) : null
  const eyebrow = [look?.label, item.topic ?? TOPIC[item.tone]].filter(Boolean).join(" · ")
  return (
    <div role={item.tone === "error" ? "alert" : "status"} className="cno-toast" data-tone={item.tone}>
      <div className="cno-toast-body">
        {look ? (
          <span className="cno-tile mono" style={{ background: look.bg, color: look.fg }} aria-hidden>
            {look.mono}
          </span>
        ) : (
          <span className="cno-tile" aria-hidden>
            {ICONS[item.tone]}
          </span>
        )}
        <div className="cno-toast-copy">
          <span className="cno-eyebrow">{eyebrow}</span>
          <span className="cno-toast-title">{item.title}</span>
          {item.description ? <span className="cno-toast-desc">{item.description}</span> : null}
          {item.action || item.cancel ? (
            <div className="cno-toast-actions">
              {item.action ? (
                <button type="button" className={`cno-btn sm ${ACTION_CLASS[item.tone] ?? "primary"}`} onClick={act(item.action.onClick)}>
                  {item.action.label}
                </button>
              ) : null}
              {item.cancel ? (
                <button type="button" className="cno-btn sm ghost" onClick={act(item.cancel.onClick)}>
                  {item.cancel.label}
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
        <button type="button" aria-label="Dismiss" className="cno-x" onClick={() => removeConnectorsToast(item.id)}>
          <X size={14} strokeWidth={2.4} aria-hidden />
        </button>
      </div>
      <div className="cno-toast-track" aria-hidden>
        {timed ? (
          <div
            key={item.createdAt}
            className="cno-toast-bar"
            style={{ animationDuration: `${item.duration}ms`, animationPlayState: paused ? "paused" : "running" }}
          />
        ) : item.tone === "loading" ? (
          <div className="cno-toast-indeterminate" />
        ) : null}
      </div>
    </div>
  )
}

/** Bottom-left stack of up to three toasts (full width on phones). Hover or focus pauses the clocks. */
export function ConnectorsToaster() {
  const [items, setItems] = useState<ConnectorsToast[]>([])
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)

  useEffect(() => registerConnectorsToaster(setItems), [])

  const paused = hovered || focused
  return (
    <section
      className="cno-toasts"
      aria-label="Connector notifications"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFocused(false)
      }}
    >
      {items.map((item) => (
        <ToastCard key={item.id} item={item} paused={paused} />
      ))}
    </section>
  )
}
