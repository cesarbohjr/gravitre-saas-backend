"use client"

import { useEffect, useRef, useState, type ReactNode } from "react"
import { Bell, Check, CircleAlert, Download, Info, Loader2, Shield, ShieldAlert, X } from "lucide-react"
import {
  registerTrustSafetyToaster,
  removeTrustSafetyToast,
  type TrustSafetyToast,
  type TrustSafetyToastTone,
} from "./toast"

const ICONS: Record<TrustSafetyToastTone, ReactNode> = {
  success: <Check size={18} strokeWidth={2.2} aria-hidden />,
  error: <CircleAlert size={18} strokeWidth={2.2} aria-hidden />,
  warning: <ShieldAlert size={18} strokeWidth={2.2} aria-hidden />,
  approval: <Shield size={18} strokeWidth={2.2} aria-hidden />,
  info: <Info size={18} strokeWidth={2.2} aria-hidden />,
  message: <Bell size={18} strokeWidth={2.2} aria-hidden />,
  loading: <Loader2 size={18} strokeWidth={2.2} className="tso-spin" aria-hidden />,
  progress: <Download size={18} strokeWidth={2.2} aria-hidden />,
}

/** Primary action colour per tone: dark for failures (Try again), green otherwise. */
const ACTION_CLASS: Partial<Record<TrustSafetyToastTone, string>> = { error: "dark" }

/** Approval toasts say what they want, whatever tab they were raised on. */
const TONE_EYEBROW: Partial<Record<TrustSafetyToastTone, string>> = { approval: "Needs your approval" }

function ToastCard({ item, fallbackEyebrow, paused }: { item: TrustSafetyToast; fallbackEyebrow: string; paused: boolean }) {
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
    const timer = window.setTimeout(() => removeTrustSafetyToast(item.id, "auto"), remaining.current)
    return () => {
      window.clearTimeout(timer)
      remaining.current = Math.max(0, remaining.current - (Date.now() - startedAt.current))
    }
  }, [paused, timed, item.id, item.createdAt])

  const act =
    (handler: (event: React.MouseEvent<HTMLButtonElement>) => void) =>
    (event: React.MouseEvent<HTMLButtonElement>) => {
      handler(event)
      if (!event.defaultPrevented) removeTrustSafetyToast(item.id)
    }

  const progress = item.tone === "progress" ? Math.max(0, Math.min(1, item.progress ?? 0)) : null

  return (
    <div role={item.tone === "error" ? "alert" : "status"} className="tso-toast" data-tone={item.tone}>
      <div className="tso-toast-body">
        <span className="tso-tile">{ICONS[item.tone]}</span>
        <div className="tso-toast-copy">
          <span className="tso-eyebrow">{item.eyebrow ?? TONE_EYEBROW[item.tone] ?? fallbackEyebrow}</span>
          <span className="tso-toast-title">{item.title}</span>
          {item.description ? <span className="tso-toast-desc">{item.description}</span> : null}
          {item.action || item.cancel ? (
            <div className="tso-toast-actions">
              {item.action ? (
                <button type="button" className={`tso-btn sm ${ACTION_CLASS[item.tone] ?? "primary"}`} onClick={act(item.action.onClick)}>
                  {item.action.label}
                </button>
              ) : null}
              {item.cancel ? (
                <button type="button" className="tso-btn sm ghost" onClick={act(item.cancel.onClick)}>
                  {item.cancel.label}
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
        <button type="button" aria-label="Dismiss" className="tso-x" onClick={() => removeTrustSafetyToast(item.id)}>
          <X size={14} strokeWidth={2.4} aria-hidden />
        </button>
      </div>
      {progress != null ? (
        <div className="tso-toast-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)}>
          <div className="tso-toast-fill" style={{ width: `${progress * 100}%` }} />
        </div>
      ) : timed ? (
        <div className="tso-toast-track" aria-hidden>
          <div
            key={item.createdAt}
            className="tso-toast-bar"
            style={{ animationDuration: `${item.duration}ms`, animationPlayState: paused ? "paused" : "running" }}
          />
        </div>
      ) : null}
    </div>
  )
}

/**
 * Bottom-left stack of up to three toasts (full width on phones). Hover or focus
 * pauses the clocks. `eyebrow` names the tab a toast came from when it does not
 * set its own.
 */
export function TrustSafetyToaster({ eyebrow }: { eyebrow: string }) {
  const [items, setItems] = useState<TrustSafetyToast[]>([])
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)

  useEffect(() => registerTrustSafetyToaster(setItems), [])

  const paused = hovered || focused
  return (
    <section
      className="tso-toasts"
      aria-label="Trust and Safety notifications"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFocused(false)
      }}
    >
      {items.map((item) => (
        <ToastCard key={item.id} item={item} fallbackEyebrow={eyebrow} paused={paused} />
      ))}
    </section>
  )
}
