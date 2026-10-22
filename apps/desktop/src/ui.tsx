import type { CSSProperties, ReactNode } from "react"
import { avatarColor, initials, STATUS, type StepState, type Status } from "./lib/model"

export const ic = {
  home: "M3 3h7v7H3z M14 3h7v7h-7z M14 14h7v7h-7z M3 14h7v7H3z",
  ask: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  assign: "M3 17l2 2 4-4 M3 7l2 2 4-4 M13 6h8 M13 12h8 M13 18h8",
  appr: "M20 13c0 5-3.5 7.5-7.7 9a1 1 0 0 1-.6 0C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.2-2.7a1.2 1.2 0 0 1 1.6 0C14.5 3.8 17 5 19 5a1 1 0 0 1 1 1z M9 12l2 2 4-4",
  act: "M22 12h-4l-3 9L9 3l-3 9H2",
  voice: "M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z M19 10v2a7 7 0 0 1-14 0v-2 M12 19v3",
  micoff: "M2 2l20 20 M18.9 13.4A7 7 0 0 0 19 12v-2 M5 10v2a7 7 0 0 0 12 5 M15 9.3V5a3 3 0 0 0-5.7-1.3 M9 9v3a3 3 0 0 0 5.1 2.1 M12 19v3",
  settings: "M21 4h-7 M10 4H3 M21 12h-9 M8 12H3 M21 20h-5 M12 20H3 M14 2v4 M8 10v4 M16 18v4",
  search: "M21 21l-4.3-4.3 M3 11a8 8 0 1 0 16 0a8 8 0 1 0 -16 0",
  plus: "M5 12h14 M12 5v14",
  bell: "M10.3 21a2 2 0 0 0 3.4 0 M3.3 15.3A1 1 0 0 0 4 17h16a1 1 0 0 0 .7-1.7C19.4 14 18 12.5 18 8A6 6 0 0 0 6 8c0 4.5-1.4 6-2.7 7.3",
  x: "M18 6 6 18 M6 6l12 12",
  ext: "M7 17 17 7 M7 7h10v10",
  play: "M6 3l14 9-14 9z",
  check: "M20 6 9 17l-5-5",
  checkc: "M2 12a10 10 0 1 0 20 0a10 10 0 1 0 -20 0 M9 12l2 2 4-4",
  clock: "M12 6v6l4 2 M2 12a10 10 0 1 0 20 0a10 10 0 1 0 -20 0",
  alert: "M2 12a10 10 0 1 0 20 0a10 10 0 1 0 -20 0 M12 8v4 M12 16h.01",
  panel: "M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M15 3v18",
  rail: "M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M9 3v18",
  clip: "M8 2h8v4H8z M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2",
  moon: "M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4 M16 17l5-5-5-5 M21 12H9",
  dot: "M12 12h.01",
  circle: "M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8",
  chevrons: "m7 15 5 5 5-5 M7 9l5-5 5 5",
  download: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M7 10l5 5 5-5 M12 15V3",
  spark: "M12 2v4 M12 18v4 M4.9 4.9l2.8 2.8 M16.3 16.3l2.8 2.8 M2 12h4 M18 12h4 M4.9 19.1l2.8-2.8 M16.3 7.7l2.8-2.8",
  stop: "M6 6h12v12H6z",
} as const

export type IconName = keyof typeof ic

export function Icon({ name, size, style, strokeWidth }: { name: IconName; size?: number; style?: CSSProperties; strokeWidth?: number }) {
  return (
    <svg
      className="ic"
      viewBox="0 0 24 24"
      aria-hidden="true"
      style={{ ...(size ? { width: size, height: size } : null), ...(strokeWidth ? { strokeWidth } : null), ...style }}
    >
      <path d={ic[name]} />
    </svg>
  )
}

export function Mark({ width = 24, height = 18 }: { width?: number; height?: number }) {
  return (
    <svg width={width} height={height} viewBox="0 0 30 22" aria-hidden="true" style={{ flex: "none" }}>
      <path d="M7 0h23l-4 6H3z M5 8h22l-4 6H1z M3 16h20l-4 6H0z" fill="#0b8a5c" />
    </svg>
  )
}

export function Avatar({ name, size = 28, color }: { name: string; size?: number; color?: string }) {
  return (
    <span
      className="av"
      aria-hidden="true"
      style={{ width: size, height: size, fontSize: Math.round(size * 0.42), background: color || avatarColor(name) }}
    >
      {initials(name)}
    </span>
  )
}

export function StatusPill({ status, label }: { status: Status; label?: string }) {
  const s = STATUS[status]
  return (
    <span className={`pill ${s.cls}`}>
      <span className="dot" />
      {label || s.label}
    </span>
  )
}

const STEP: Record<StepState, [string, IconName]> = {
  done: ["st-done", "check"],
  running: ["st-run", "dot"],
  waiting: ["st-wait", "clock"],
  queued: ["st-q", "circle"],
  failed: ["st-fail", "x"],
}

export function StepDot({ state }: { state: StepState }) {
  const [cls, name] = STEP[state]
  return (
    <span className={`stp ${cls}`}>
      <Icon name={name} size={12} strokeWidth={2} />
    </span>
  )
}

export function Logo({ text, style }: { text: string; style?: CSSProperties }) {
  if (!text) return null
  return (
    <span className="logo" style={style}>
      {text}
    </span>
  )
}

export function Toggle({ on, label, onChange, disabled }: { on: boolean; label: string; onChange: (next: boolean) => void; disabled?: boolean }) {
  return (
    <button
      className={`tog ${on ? "on" : ""}`}
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!on)}
    />
  )
}

export function Card({ title, sub, action, children, style }: { title: string; sub?: string; action?: ReactNode; children: ReactNode; style?: CSSProperties }) {
  return (
    <section className="card" style={{ overflow: "hidden", ...style }}>
      <div className="band" style={{ padding: "14px 18px", display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          <span style={{ fontSize: 15, fontWeight: 600 }}>{title}</span>
          {sub ? <span className="sub">{sub}</span> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

export function PageHead({ eyebrow, title, lede, children }: { eyebrow: string; title: string; lede: string; children?: ReactNode }) {
  return (
    <div className="phead">
      <div style={{ flex: 1, minWidth: 300, display: "flex", flexDirection: "column", gap: 10 }}>
        <span className="eyebrow">{eyebrow}</span>
        <h1 className="h1">{title}</h1>
        <p className="lede">{lede}</p>
      </div>
      {children}
    </div>
  )
}

export function Live({ at }: { at: number | null }) {
  const label = at == null ? "Connecting…" : Date.now() - at < 60_000 ? "Live · updated just now" : `Live · updated ${Math.floor((Date.now() - at) / 60000)}m ago`
  return (
    <span className="live">
      <span className="dot" style={{ background: at == null ? "var(--bx)" : "var(--ok)" }} />
      {label}
    </span>
  )
}

export function Empty({ title, body, icon = "check" }: { title: string; body: string; icon?: IconName }) {
  return (
    <div style={{ padding: "48px 16px", textAlign: "center", display: "flex", flexDirection: "column", gap: 8, alignItems: "center" }}>
      <span
        style={{
          width: 52,
          height: 52,
          borderRadius: "50%",
          background: "var(--brs)",
          color: "var(--brk)",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Icon name={icon} size={20} />
      </span>
      <span style={{ fontSize: 17, fontWeight: 600 }}>{title}</span>
      <span style={{ fontSize: 14, color: "var(--t2)", maxWidth: 420 }}>{body}</span>
    </div>
  )
}

export function ErrorLine({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 16px", borderRadius: 12, background: "var(--dgs)", color: "var(--dgk)", fontSize: 13 }}>
      <Icon name="alert" />
      <span style={{ flex: 1 }}>{message}</span>
      {onRetry ? (
        <button className="btn btn-sm" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  )
}

export const isMac = typeof navigator !== "undefined" && /mac/i.test(navigator.userAgent)
export const MOD = isMac ? "⌘" : "Ctrl"
export const ALT = isMac ? "⌥" : "Alt"
export const SHIFT = isMac ? "⇧" : "Shift"
