"use client"

/**
 * Building blocks for the redesigned Settings, Audit trail and Environments
 * pages (settings-kit.css, scoped under .gv-set by SettingsShell).
 */
import type { ComponentType, ReactNode } from "react"
import { Info } from "lucide-react"
import { pageWindow } from "@/components/workspace/au-pages"
import { cn } from "@/lib/utils"

type Tone = "green" | "mute" | "warn" | "bad" | "blue"
type PillTone = "green" | "amber" | "red" | "blue" | "neutral" | "white"
type IconType = ComponentType<{ size?: number | string; className?: string; "aria-hidden"?: boolean }>

/** Icon chip: green by default, mute / warn / bad / blue tones. */
export function SetIco({
  icon: Icon,
  tone = "green",
  size = "md",
  className,
}: {
  icon: IconType
  tone?: Tone
  size?: "xs" | "sm" | "md" | "lg"
  className?: string
}) {
  const px = size === "lg" ? 22 : size === "xs" ? 15 : 18
  return (
    <span className={cn("gs-ico", tone !== "green" && tone, size !== "md" && size, className)} aria-hidden>
      <Icon size={px} aria-hidden />
    </span>
  )
}

export function SetPill({
  tone = "neutral",
  dot,
  live,
  children,
  className,
}: {
  tone?: PillTone
  /** Show a status dot in the pill's colour. */
  dot?: boolean
  /** Pulse the dot (running, syncing, live). */
  live?: boolean
  children: ReactNode
  className?: string
}) {
  const dotTone = tone === "green" ? "green" : tone === "amber" ? "amber" : tone === "red" ? "red" : tone === "blue" ? "blue" : "ghost"
  return (
    <span className={cn("gs-pill", tone !== "neutral" && tone, className)}>
      {dot || live ? <span className={cn("gs-dot", dotTone, live && "gs-live")} aria-hidden /> : null}
      {children}
    </span>
  )
}

export function SetSwitch({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean
  onChange: (next: boolean) => void
  label: string
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-label={label}
      aria-checked={checked}
      disabled={disabled}
      className="gs-sw"
      onClick={() => onChange(!checked)}
    />
  )
}

export interface SetTabOption<T extends string> {
  id: T
  label: ReactNode
  icon?: IconType
  count?: number | string
  disabled?: boolean
}

/** Segmented view toggle (aria-pressed) or tab list (role="tab", aria-selected). */
export function SetTabs<T extends string>({
  value,
  options,
  onChange,
  label,
  mode = "toggle",
  className,
}: {
  value: T
  options: SetTabOption<T>[]
  onChange: (next: T) => void
  label: string
  mode?: "toggle" | "tabs"
  className?: string
}) {
  return (
    <div className={cn("gs-tabs", className)} role={mode === "tabs" ? "tablist" : "group"} aria-label={label}>
      {options.map((option) => {
        const on = option.id === value
        const Icon = option.icon
        return (
          <button
            key={option.id}
            type="button"
            className="gs-tab"
            disabled={option.disabled}
            role={mode === "tabs" ? "tab" : undefined}
            aria-selected={mode === "tabs" ? on : undefined}
            aria-pressed={mode === "toggle" ? on : undefined}
            onClick={() => onChange(option.id)}
          >
            {Icon ? <Icon size={15} aria-hidden /> : null}
            {option.label}
            {option.count !== undefined ? <span className="gs-count">{option.count}</span> : null}
          </button>
        )
      })}
    </div>
  )
}

/** Stat tile from the design (icon, label, big number, hint). `value === null` renders "None yet". */
export function SetStat({
  icon,
  tone = "mute",
  label,
  value,
  hint,
  onClick,
  pressed,
}: {
  icon: IconType
  tone?: Tone
  label: string
  value: ReactNode | null
  hint?: ReactNode
  onClick?: () => void
  pressed?: boolean
}) {
  const body = (
    <>
      <SetIco icon={icon} tone={tone} size="sm" />
      <div style={{ minWidth: 0 }}>
        <div className="l">{label}</div>
        <div className={cn("v", value === null && "none")}>{value === null ? "None yet" : value}</div>
        {hint ? <div className="h">{hint}</div> : null}
      </div>
    </>
  )
  if (onClick) {
    return (
      <button type="button" className="gs-stat" onClick={onClick} aria-pressed={pressed}>
        {body}
      </button>
    )
  }
  return <div className="gs-stat">{body}</div>
}

export function SetNote({
  children,
  tone,
  icon: Icon = Info,
  className,
}: {
  children: ReactNode
  tone?: "white" | "green" | "amber" | "red"
  icon?: IconType
  className?: string
}) {
  return (
    <div className={cn("gs-note", tone, className)}>
      <Icon size={17} aria-hidden />
      <div style={{ minWidth: 0, flex: 1 }}>{children}</div>
    </div>
  )
}

/**
 * Illustration in the design's frame. `ratio` is width / height, e.g. "320 / 170".
 * Pass a static scene by `name`, or an animated art component as children.
 */
export function SetArt({
  name,
  ratio = "320 / 170",
  className,
  style,
  children,
}: {
  name?: string
  ratio?: string
  className?: string
  style?: React.CSSProperties
  children?: React.ReactNode
}) {
  return (
    <div className={cn("gs-art", className)} style={{ aspectRatio: ratio, ...(children ? { position: "relative" } : null), ...style }}>
      {children ?? (
        // eslint-disable-next-line @next/next/no-img-element -- static animated SVG scene
        <img src={`/illustrations/${name}.svg`} alt="" aria-hidden loading="lazy" decoding="async" data-illustration={name} />
      )}
    </div>
  )
}

/** "Showing 1 to 10 of 66" plus ‹ Prev 1 2 3 4 … 66 Next ›. */
export function SetPager({
  page,
  pageCount,
  from,
  to,
  total,
  onPage,
  noun,
}: {
  page: number
  pageCount: number
  from: number
  to: number
  total: number
  onPage: (page: number) => void
  noun?: string
}) {
  return (
    <div className="gs-foot">
      <span>
        Showing{" "}
        <strong>
          {from} to {to}
        </strong>{" "}
        of {total.toLocaleString()}
        {noun ? ` ${noun}` : ""}
      </span>
      {pageCount > 1 ? (
        <nav aria-label="Pagination" className="gs-pager">
          <button type="button" className="gs-pg" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page">
            ‹ Prev
          </button>
          {pageWindow(page, pageCount).map((n, index) =>
            n === null ? (
              <span key={`gap-${index}`} className="gs-pg gap" aria-hidden>
                …
              </span>
            ) : (
              <button
                key={n}
                type="button"
                className="gs-pg"
                aria-current={n === page ? "page" : undefined}
                aria-label={`Page ${n}`}
                onClick={() => onPage(n)}
              >
                {n}
              </button>
            ),
          )}
          <button
            type="button"
            className="gs-pg"
            disabled={page >= pageCount}
            onClick={() => onPage(page + 1)}
            aria-label="Next page"
          >
            Next ›
          </button>
        </nav>
      ) : null}
    </div>
  )
}

/** Loading placeholder rows inside a card. */
export function SetSkeleton({ rows = 3, label = "Loading" }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-label={label} style={{ display: "grid", gap: 10, padding: 20 }}>
      {Array.from({ length: rows }, (_, i) => (
        <span key={i} className="gs-skel" style={{ height: 18, width: `${90 - i * 12}%` }} />
      ))}
    </div>
  )
}

/** Inline error with a retry button, inside a card or section. */
export function SetError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="gs-empty">
      <b>{message}</b>
      {onRetry ? (
        <button type="button" className="gs-btn line sm" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  )
}

/** Initials for an avatar chip. */
export function initialsOf(name: string | null | undefined, fallback = "?"): string {
  const words = String(name ?? "")
    .replace(/[^\p{L}\p{N}\s'-]/gu, " ")
    .split(/\s+/)
    .filter(Boolean)
  if (!words.length) return fallback
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
  return (words[0][0] + words[1][0]).toUpperCase()
}

/** Stable avatar tone class (t0..t5) from any id or name. */
export function avatarTone(seed: string | null | undefined): string {
  const text = String(seed ?? "")
  let hash = 0
  for (let i = 0; i < text.length; i += 1) hash = (hash * 31 + text.charCodeAt(i)) >>> 0
  return `t${hash % 6}`
}

/** "Oct 18, 2026" from an ISO string; null when missing or invalid. */
export function formatDay(iso: string | null | undefined): string | null {
  if (!iso) return null
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

/** "Oct 18, 9:34 pm" from an ISO string; null when missing or invalid. */
export function formatMoment(iso: string | null | undefined): string | null {
  if (!iso) return null
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
}

/** "41 minutes ago" style relative time; null when missing or invalid. */
export function formatAgo(iso: string | null | undefined, now = Date.now()): string | null {
  if (!iso) return null
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return null
  const s = Math.max(0, Math.round((now - t) / 1000))
  if (s < 60) return "just now"
  const m = Math.round(s / 60)
  if (m < 60) return `${m} minute${m === 1 ? "" : "s"} ago`
  const h = Math.round(m / 60)
  if (h < 24) return `${h} hour${h === 1 ? "" : "s"} ago`
  const d = Math.round(h / 24)
  if (d < 30) return `${d} day${d === 1 ? "" : "s"} ago`
  return formatDay(iso)
}

/**
 * Page header for a settings section that renders its own header (use with
 * SettingsShell hideHeader): crumb, title, lede and actions on the right.
 */
export function SetHeader({
  crumb,
  title,
  description,
  actions,
}: {
  crumb: ReactNode
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="gs-head">
      <div>
        <span className="gs-crumb">{crumb}</span>
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="gs-head-actions">{actions}</div> : null}
    </div>
  )
}
