import type { CSSProperties, ReactNode } from "react"
import { avatarColor, initials, STATUS, type StepState, type Status } from "./lib/model"
import type { AgentIdentity } from "./lib/identity"

export const ic = {
  home: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z",
  ask: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  assign: "M3 17l2 2 4-4 M3 7l2 2 4-4 M13 6h8 M13 12h8 M13 18h8",
  appr: "M20 13c0 5-3.5 7.5-7.7 9a1 1 0 0 1-.6 0C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.2-2.7a1.2 1.2 0 0 1 1.6 0C14.5 3.8 17 5 19 5a1 1 0 0 1 1 1z M9 12l2 2 4-4",
  act: "M22 12h-4l-3 9L9 3l-3 9H2",
  micoff: "M2 2l20 20 M9 9v3a3 3 0 0 0 5.1 2.1 M15 9.3V5a3 3 0 0 0-5.9-.7 M17 16.9A7 7 0 0 1 5 12v-2 M19 10v2a7 7 0 0 1-.1 1.2 M12 19v3",
  voice: "M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z M19 10v2a7 7 0 0 1-14 0v-2 M12 19v3",
  settings: "M21 4h-7 M10 4H3 M21 12h-9 M8 12H3 M21 20h-5 M12 20H3 M14 2v4 M8 10v4 M16 18v4",
  search: "M21 21l-4.3-4.3 M3 11a8 8 0 1 0 16 0a8 8 0 1 0 -16 0",
  plus: "M5 12h14 M12 5v14",
  edit: "M12 20h9 M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z",
  x: "M18 6 6 18 M6 6l12 12",
  ext: "M7 17 17 7 M7 7h10v10",
  up: "M12 19V5 M5 12l7-7 7 7",
  play: "M7 4l12 8-12 8z",
  pause: "M8 5v14 M16 5v14",
  stop: "M6 6h12v12H6z",
  check: "M20 6 9 17l-5-5",
  checkc: "M2 12a10 10 0 1 0 20 0a10 10 0 1 0 -20 0 M8.5 12l2.5 2.5 4.5-5",
  clock: "M12 7v5l3 2 M2 12a10 10 0 1 0 20 0a10 10 0 1 0 -20 0",
  alert: "M2 12a10 10 0 1 0 20 0a10 10 0 1 0 -20 0 M12 8v4 M12 16h.01",
  panel: "M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M15 3v18",
  clip: "M8 2h8v4H8z M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2",
  camera: "M3 8a2 2 0 0 1 2-2h2l2-3h6l2 3h2a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M12 10a3.5 3.5 0 1 0 0 7a3.5 3.5 0 1 0 0-7z",
  paperclip: "M21 11.5l-8.6 8.6a5 5 0 0 1-7.1-7.1l8.6-8.6a3.3 3.3 0 0 1 4.7 4.7l-8.6 8.6a1.7 1.7 0 0 1-2.4-2.4l7.9-7.9",
  globe: "M2 12a10 10 0 1 0 20 0a10 10 0 1 0 -20 0 M2 12h20 M12 2a15 15 0 0 1 0 20 M12 2a15 15 0 0 0 0 20",
  monitor: "M3 4h18v12H3z M8 20h8 M12 16v4",
  puzzle: "M9 3h6v3a1.5 1.5 0 1 0 3 0V6h3v6h-3a1.5 1.5 0 1 0 0 3h3v6H3v-6h3a1.5 1.5 0 1 0 0-3H3V6h3",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4 M16 17l5-5-5-5 M21 12H9",
  dot: "M12 12h.01",
  circle: "M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8",
  chevrons: "m7 15 5 5 5-5 M7 9l5-5 5 5",
  chevr: "M9 6l6 6-6 6",
  download: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M7 10l5 5 5-5 M12 15V3",
  expand: "M15 3h6v6 M9 21H3v-6 M21 3l-7 7 M3 21l7-7",
  bell: "M10.3 21a2 2 0 0 0 3.4 0 M3.3 15.3A1 1 0 0 0 4 17h16a1 1 0 0 0 .7-1.7C19.4 14 18 12.5 18 8A6 6 0 0 0 6 8c0 4.5-1.4 6-2.7 7.3",
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

/** A raw 24x24 stroke path (department icons). */
export function PathIcon({ d, size = 16, style }: { d: string; size?: number; style?: CSSProperties }) {
  return (
    <svg className="ic" viewBox="0 0 24 24" aria-hidden="true" style={{ width: size, height: size, ...style }}>
      <path d={d} />
    </svg>
  )
}

const MARK_BAR = "M6 160C1 160-2 156 1 152L59 72C91 27 138 0 186 0H628C636 0 640 6 635 13L576 94C543 137 498 160 450 160Z"

/** The Gravitre two-bar mark, the same one the web app's sidebar shows. */
export function Mark({ width = 24, height = 14, color = "var(--br)" }: { width?: number; height?: number; color?: string }) {
  return (
    <svg width={width} height={height} viewBox="0 0 640 367" aria-hidden="true" fill="currentColor" style={{ flex: "none", color }}>
      <path d={MARK_BAR} />
      <path d={MARK_BAR} transform="translate(0 207)" />
    </svg>
  )
}

/** The app tile: the mark in white on carbon. */
export function MarkTile({ size = 24 }: { size?: number }) {
  return (
    <span className="mark" style={{ width: size, height: size, borderRadius: Math.round(size / 4) }}>
      <Mark width={Math.round(size * 0.58)} height={Math.round(size * 0.34)} color="#ffffff" />
    </span>
  )
}

/** People: initials on a color. */
export function Avatar({ name, size = 28, color }: { name: string; size?: number; color?: string }) {
  return (
    <span
      className="av"
      aria-hidden="true"
      style={{ width: size, height: size, fontSize: Math.round(size * 0.4), background: color || avatarColor(name) }}
    >
      {initials(name)}
    </span>
  )
}

/** Agents: their department icon in the department color, the same on every surface. */
export function AgentAvatar({ id, size = 28 }: { id: AgentIdentity; size?: number }) {
  return (
    <span className="av aav" aria-hidden="true" title={`${id.name} · ${id.dept.label}`} style={{ width: size, height: size, color: id.dept.color }}>
      <PathIcon d={id.dept.icon} size={Math.round(size * 0.55)} />
    </span>
  )
}

/** The workspace tile: its initial on a stable color. */
export function WorkspaceTile({ name, size = 24 }: { name: string; size?: number }) {
  return (
    <span className="wstile" aria-hidden="true" style={{ width: size, height: size, background: avatarColor(`ws:${name}`), fontSize: Math.round(size * 0.46) }}>
      {(name.trim()[0] || "W").toUpperCase()}
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

/** A card section with the design's compact header row. */
export function Section({ title, count, action, children, style }: { title: string; count?: number | null; action?: ReactNode; children: ReactNode; style?: CSSProperties }) {
  return (
    <section className="card" style={{ overflow: "hidden", ...style }}>
      <div className="sech">
        <h2>{title}</h2>
        {count ? (
          <span className="pill" style={{ background: "var(--aps)", color: "var(--apk)" }}>
            {count}
          </span>
        ) : null}
        {action}
      </div>
      {children}
    </section>
  )
}

/** Library illustration for empty states. */
export function Art({ src, width, style }: { src: string; width: number; style?: CSSProperties }) {
  return (
    <span className="art" style={{ width, ...style }}>
      <img src={src} alt="" draggable={false} />
    </span>
  )
}

export function Empty({ title, body, art }: { title: string; body: string; art?: string }) {
  return (
    <div style={{ padding: "32px 16px", textAlign: "center", display: "flex", flexDirection: "column", gap: 6, alignItems: "center", margin: "auto" }}>
      {art ? <Art src={art} width={200} style={{ marginBottom: 8 }} /> : null}
      <span style={{ fontSize: 15, fontWeight: 600 }}>{title}</span>
      <span style={{ fontSize: 13, color: "var(--t2)", maxWidth: 380 }}>{body}</span>
    </div>
  )
}

export function ErrorLine({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 10, background: "var(--dgs)", color: "var(--dgk)", fontSize: 13 }}>
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
