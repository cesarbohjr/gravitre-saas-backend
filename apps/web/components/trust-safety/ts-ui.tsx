"use client"

import type { CSSProperties, ReactNode } from "react"
import { TrustSafetyArt, type TrustSafetyArtKind } from "./trust-safety-art"

/** Shared pieces of the Trust & Safety design (classes live in gv-trust.css). */

const ICON_PATHS = {
  check: <><circle cx="12" cy="12" r="8.5" /><path d="m8.5 12 2.5 2.5 4.5-5" /></>,
  list: <><path d="M9 6h11M9 12h11M9 18h11" /><path d="m3.5 6 1 1 2-2M3.5 12l1 1 2-2M3.5 18l1 1 2-2" /></>,
  shieldCheck: <><path d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6z" /><path d="m9 12 2 2 4-4" /></>,
  shield: <path d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6z" />,
  lock: <><rect x="4.5" y="10" width="15" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>,
  users: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c1-3.5 3.5-5.5 6.5-5.5s5.5 2 6.5 5.5" /><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14.8c1.8.8 3 2.6 3.5 5.2" /></>,
  servers: <><rect x="4" y="4" width="16" height="7" rx="2" /><rect x="4" y="13" width="16" height="7" rx="2" /><path d="M8 7.5h.01M8 16.5h.01" /></>,
  clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></>,
  warn: <><path d="M12 4 2.5 20h19z" /><path d="M12 10v4.5M12 17.5h.01" /></>,
  globe: <><circle cx="12" cy="12" r="8.5" /><path d="M3.5 12h17M12 3.5c2.5 2.5 3.5 5.5 3.5 8.5s-1 6-3.5 8.5c-2.5-2.5-3.5-5.5-3.5-8.5s1-6 3.5-8.5z" /></>,
  agent: <><rect x="4" y="7" width="16" height="13" rx="3" /><path d="M12 7V4M9 13h.01M15 13h.01M9.5 17h5" /></>,
  route: <path d="M4 7h11M4 12h7M4 17h11M17 9l3 3-3 3" />,
  info: <><circle cx="12" cy="12" r="8.5" /><path d="M12 11v5M12 8h.01" /></>,
  download: <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />,
  search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>,
  csv: <><path d="M7 3h7l4 4v14H7z" /><path d="M10 12h5M10 16h5" /></>,
  json: <><path d="M7 3h7l4 4v14H7z" /><path d="M11 11c-1 0-1 1-1 2s-1 1-1 1 1 0 1 1 0 2 1 2M14 11c1 0 1 1 1 2s1 1 1 1-1 0-1 1 0 2-1 2" /></>,
  events: <><path d="M9 6h11M9 12h11M9 18h11" /><path d="M4 6h.01M4 12h.01M4 18h.01" /></>,
  chat: <path d="M5 5h14v10H9l-4 4z" />,
  up: <path d="M12 19V5M6 11l6-6 6 6" />,
  tick: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  dash: <path d="M5 12h14" />,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  plus: <path d="M12 5v14M5 12h14" />,
  key: <><circle cx="8" cy="15" r="4" /><path d="m10.8 12.2 8.7-8.7M16 6l2.5 2.5M14 8l2 2" /></>,
  keySm: <><circle cx="8" cy="15" r="4" /><path d="m10.8 12.2 8.7-8.7M16 6l2.5 2.5" /></>,
  copy: <><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" /></>,
  forward: <><path d="M4 12h11M11 7l5 5-5 5" /><path d="M19 5v14" /></>,
} as const

export type IconName = keyof typeof ICON_PATHS

export function Icon({
  name,
  size = 18,
  stroke = "currentColor",
  width = 1.8,
  style,
}: {
  name: IconName
  size?: number
  stroke?: string
  width?: number
  style?: CSSProperties
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={stroke}
      strokeWidth={width}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={style}
    >
      {ICON_PATHS[name]}
    </svg>
  )
}

export function Switch({ on, label, onToggle, disabled }: { on: boolean; label: string; onToggle: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-label={label}
      aria-checked={on}
      disabled={disabled}
      className={`ts-sw${on ? " on" : ""}`}
      onClick={onToggle}
    />
  )
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T
  options: ReadonlyArray<readonly [T, string]>
  onChange: (next: T) => void
  label: string
}) {
  return (
    <div className="ts-tabs" role="group" aria-label={label}>
      {options.map(([id, text]) => (
        <button key={id} type="button" className={`ts-tab${value === id ? " on" : ""}`} aria-pressed={value === id} onClick={() => onChange(id)}>
          {text}
        </button>
      ))}
    </div>
  )
}

export type HeroTile = { value: ReactNode; label: string; tone?: "good" | "bad"; muted?: boolean }

export function Hero({
  art,
  eyebrow,
  big,
  bigColor,
  unit,
  bars,
  advice,
  actions,
  tiles,
}: {
  art: TrustSafetyArtKind
  eyebrow: string
  big: ReactNode
  bigColor?: string
  unit: string
  /** Progress segments: true is filled. */
  bars?: boolean[]
  advice: ReactNode
  actions?: ReactNode
  tiles: HeroTile[]
}) {
  return (
    <section className="ts-card ts-hero ts-rise">
      <TrustSafetyArt kind={art} />
      <div className="ts-hsum">
        <div className="ts-eyebrow">{eyebrow}</div>
        <div className="ts-metric">
          <span className="big" style={bigColor ? { color: bigColor } : undefined}>{big}</span>
          <span className="unit">{unit}</span>
        </div>
        {bars ? (
          <div style={{ display: "flex", gap: 6, marginTop: 12 }} aria-hidden="true">
            {bars.map((filled, i) => (
              <span
                key={i}
                className="ts-bar"
                style={{ flex: 1, height: 8, borderRadius: 4, background: filled ? "#19C37D" : "#E4E4DF", animationDelay: `${i * 90}ms` }}
              />
            ))}
          </div>
        ) : null}
        <p>{advice}</p>
        {actions ? <div className="ts-hact">{actions}</div> : null}
      </div>
      <div className="ts-htiles">
        {tiles.map((t) => (
          <div key={t.label} className={`ts-tile${t.tone ? ` ${t.tone}` : ""}`}>
            <span className="v" style={t.muted ? { color: "#6A6B64" } : undefined}>{t.value}</span>
            <span className="l">{t.label}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

export function Pill({ bg, fg, dot, live, children, style }: { bg: string; fg: string; dot?: string; live?: boolean; children: ReactNode; style?: CSSProperties }) {
  return (
    <span className="ts-pill" style={{ background: bg, color: fg, ...style }}>
      {dot ? <span className={`ts-dot${live ? " ts-live" : ""}`} style={{ background: dot }} /> : null}
      {children}
    </span>
  )
}

export const TONE = {
  bad: { bg: "#F8E3E4", fg: "#8A2530", dot: "#C4434F", ico: "ts-ico bad" },
  warn: { bg: "#FBF1DC", fg: "#8A5A06", dot: "#E2A33A", ico: "ts-ico warn" },
  ok: { bg: "#E8F5EE", fg: "#1F6B42", dot: "#2E9E5B", ico: "ts-ico" },
  mute: { bg: "#EFEFEA", fg: "#55564F", dot: "#8A8B85", ico: "ts-ico mute" },
} as const

export function Note({ children }: { children: ReactNode }) {
  return (
    <div className="ts-note">
      <Icon name="shieldCheck" size={16} stroke="#0B8A5C" style={{ flex: "0 0 auto", marginTop: 2 }} />
      <span>{children}</span>
    </div>
  )
}

export const muted: CSSProperties = { fontSize: 13, color: "#6A6B64", marginTop: 2 }
