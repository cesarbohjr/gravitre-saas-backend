"use client"

/**
 * Overview sections, built to the 10-30 "Intelligence · Overview" design:
 * data readiness (with its hide/unhide details), at a glance, what Gravitre
 * knows / is learning / needs you for, how Gravitre thinks (with the seven
 * abilities toggle) and recent insights and activity (with the analysis
 * banner). Markup and classes follow the design (overview.css); every number
 * comes from overview-model.ts, and a missing one shows as a dash.
 */
import { useState, type CSSProperties, type ReactNode } from "react"
import Link from "next/link"
import { formatHours } from "@/components/intelligence/impact/impact-model"
import {
  FEED_FILTERS,
  READINESS_TIERS,
  appName,
  formatMoneyCompact,
  type Ability,
  type AttentionItem,
  type DataReadiness,
  type FeedItem,
  type FeedKind,
  type GlanceCard,
  type ReadinessArea,
} from "@/components/intelligence/overview/overview-model"
import type { PromotionCandidate } from "@/lib/api"
import type { Connector } from "@/types/api"
import "./overview.css"

// ---------------------------------------------------------------- shared bits

export const IO_TEXT = {
  body: { color: "#33342F" } as CSSProperties,
  muted: { color: "#55564F" } as CSSProperties,
  faint: { color: "#8A8B85" } as CSSProperties,
}

export function Ico({
  d,
  size = 14,
  width = 2,
  round = false,
  style,
}: {
  d: string
  size?: number
  width?: number
  round?: boolean
  style?: CSSProperties
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={width}
      strokeLinecap={round ? "round" : undefined}
      strokeLinejoin={round ? "round" : undefined}
      aria-hidden
      style={style}
    >
      <path d={d} />
    </svg>
  )
}

export const PATHS = {
  arrow: "M5 12h14M13 6l6 6-6 6",
  chevron: "m6 9 6 6 6-6",
  close: "M6 6l12 12M18 6 6 18",
  spark: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z",
  sparks: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM18.5 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z",
  chat: "M5 5h14v10H9l-4 4z",
  play: "M7 4.5v15l12-7.5z",
  shield: "M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z",
  share: "M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7M16 6l-4-4-4 4M12 2v13",
  team: "M16 19v-1a4 4 0 0 0-8 0v1M12 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM20 19v-1a3 3 0 0 0-3-3M4 19v-1a3 3 0 0 1 3-3",
  thumb: "M7 11v9H4v-9zM7 11l4-8c1.5 0 2.5 1 2.5 2.5V9h5.2a2 2 0 0 1 2 2.3l-1.2 7A2 2 0 0 1 17.5 20H7",
  know: "M5 6c0-1.4 3.1-2.6 7-2.6s7 1.2 7 2.6v12c0 1.4-3.1 2.6-7 2.6S5 19.4 5 18zM5 6c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6",
}

/** Feed kinds in the design's colors and icons. */
export const KIND: Record<FeedKind, { label: string; bg: string; fg: string; path: string }> = {
  recommendation: { label: "Recommendation", bg: "#F3FBF7", fg: "#0A6B47", path: PATHS.spark },
  action: { label: "Action", bg: "#EEF2FF", fg: "#2B59E0", path: "M5 12l4 4L19 6" },
  insight: {
    label: "Insight",
    bg: "#FBF1DC",
    fg: "#8A5A06",
    path: "M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z",
  },
  outcome: { label: "Outcome", bg: "#EFEFEA", fg: "#33342F", path: "M4 19h16M7 15l3-4 3 3 5-7" },
}

/** Glance tiles in the design's colors and icons. */
export const GLANCE_LOOK: Record<GlanceCard["id"], { bg: string; fg: string; path: string }> = {
  revenue: {
    bg: "#DDF3E8",
    fg: "#0A6B47",
    path: "M12 2v20M17 6.5c0-1.9-2.2-3.5-5-3.5S7 4.3 7 6.5 9 9.6 12 10.4s5 1.9 5 4.1-2.2 3.5-5 3.5-5-1.6-5-3.5",
  },
  hours: { bg: "#EEF2FF", fg: "#2B59E0", path: "M12 7v5l3 2M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z" },
  resolved: { bg: "#F3FBF7", fg: "#0B8A5C", path: "M5 12l4 4L19 6" },
  approval: { bg: "#FBF1DC", fg: "#8A5A06", path: "M12 8v4l2.5 2.5M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z" },
}

const LOGOS = new Set(["gmail", "hubspot", "microsoft_teams", "outlook", "slack", "stripe", "zendesk"])
const BRAND: Record<string, string> = {
  hubspot: "#FF7A59",
  zendesk: "#03363D",
  gmail: "#EA4335",
  stripe: "#635BFF",
  slack: "#4A154B",
  salesforce: "#00A1E0",
  outlook: "#0F6CBD",
  microsoft_teams: "#5B5FC7",
  intercom: "#1F8DED",
  quickbooks: "#2CA01C",
}

export function vendorKey(vendor: string): string {
  const v = vendor.toLowerCase().replace(/[\s-]+/g, "_")
  if (v === "teams") return "microsoft_teams"
  if (v === "google_mail") return "gmail"
  return v
}

export function brandColor(vendor: string): string {
  return BRAND[vendorKey(vendor)] ?? "#8A8B85"
}

/** Small round app mark: the vendor's logo when we ship one, else its initial. */
export function AppDot({ vendor, name, size }: { vendor: string; name: string; size?: number }) {
  const key = vendorKey(vendor)
  const box = size ? { width: size, height: size, fontSize: Math.round(size * 0.45) } : {}
  if (LOGOS.has(key)) {
    return (
      <span
        className="io-appdot"
        aria-hidden
        style={{
          ...box,
          background: `#FFFFFF url(/connector-logos/${key}.svg) center / 62% no-repeat`,
          boxShadow: "inset 0 0 0 1px #E4E4DF",
        }}
      />
    )
  }
  return (
    <span className="io-appdot" aria-hidden style={{ ...box, background: brandColor(vendor) }}>
      {name.charAt(0).toUpperCase()}
    </span>
  )
}

function dash(loading: boolean): string {
  return loading ? "…" : "—"
}

export function relativeTime(at: number | null, now: number = Date.now()): string {
  if (at == null) return ""
  const minutes = Math.round((now - at) / 60_000)
  if (minutes < 1) return "just now"
  if (minutes < 60) return `${minutes} ${minutes === 1 ? "minute" : "minutes"} ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} ${hours === 1 ? "hour" : "hours"} ago`
  const days = Math.round(hours / 24)
  if (days === 1) return "Yesterday"
  if (days < 7) return `${days} days ago`
  return new Date(at).toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

function SectionHead({ id, title, sub }: { id: string; title: string; sub: string }) {
  return (
    <div>
      <h2 id={id} className="io-h2">
        {title}
      </h2>
      <p className="io-sub">{sub}</p>
    </div>
  )
}

// ---------------------------------------------------------------- data readiness

const DEPTH_STYLE: Record<ReadinessArea["depth"], CSSProperties> = {
  Good: { background: "#DDF3E8", color: "#0A6B47" },
  Partial: { background: "#FBF1DC", color: "#8A5A06" },
  Missing: { background: "#EFEFEA", color: "#55564F" },
}

export function DataReadinessCard({
  readiness,
  areas,
  loading,
  href,
}: {
  readiness: DataReadiness
  areas: ReadinessArea[]
  loading: boolean
  href: string
}) {
  const [open, setOpen] = useState(false)
  const reached = READINESS_TIERS.findIndex((t) => t.id === readiness.tier)
  const next = areas.find((a) => a.depth === "Missing")
  const linked = areas.filter((a) => a.depth !== "Missing").length
  return (
    <section aria-labelledby="dr-h" className="io-card dr-card io-rise">
      <div className="dr-top">
        <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: "1 1 320px", minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <h2 id="dr-h" style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>
              Data readiness
            </h2>
            <span className="dr-badge">{loading ? "Checking" : readiness.label}</span>
          </div>
          <span data-io-muted style={{ fontSize: 14, lineHeight: 1.5, ...IO_TEXT.muted }}>
            {loading ? "Checking which apps Gravitre can read…" : readiness.summary}
          </span>
        </div>
        <div
          className="dr-meter"
          role="img"
          aria-label={`Analysis depth: ${readiness.label.toLowerCase()}, step ${reached + 1} of ${READINESS_TIERS.length}`}
        >
          {READINESS_TIERS.map((tier, i) => (
            <div key={tier.id} className="dr-step">
              <span className={i <= reached ? "dr-seg on" : "dr-seg"} />
              <span className={i === reached ? "dr-l on" : "dr-l"}>{tier.label}</span>
            </div>
          ))}
        </div>
        <button
          type="button"
          className="io-link"
          style={{ fontSize: 13 }}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "Hide details" : "See what is ready"}
        </button>
      </div>
      {open ? (
        <div className="dr-body">
          <div className="dr-areas">
            {areas.map((a) => (
              <div key={a.name} className="dr-area">
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                  <span style={{ fontSize: 13.5, fontWeight: 600 }}>{a.name}</span>
                  <span className="dr-depth" style={DEPTH_STYLE[a.depth]}>
                    {a.depth}
                  </span>
                </div>
                <div className="dr-gauge">
                  <span style={{ width: `${a.level * 25}%`, background: a.depth === "Partial" ? "#E2A33A" : "#19C37D" }} />
                </div>
                <span data-io-muted style={{ fontSize: 12.5, lineHeight: 1.4, ...IO_TEXT.muted }}>
                  {a.src}
                </span>
              </div>
            ))}
          </div>
          <div className="dr-foot">
            <div className="dr-link">
              <span className="io-dot" style={{ background: linked >= 2 ? "#19C37D" : "#E2A33A" }} />
              <span>
                {linked >= 2
                  ? `${linked} business areas have a connected app. Gravitre doesn't match records across apps into one count yet, so it doesn't claim how many accounts they share. One rich source gives value on its own; apps from different areas unlock broader findings.`
                  : "One rich source gives value on its own; apps from different areas unlock broader findings."}
              </span>
            </div>
            <div className="dr-next">
              <span style={{ flex: 1 }}>
                {next
                  ? `Connect ${next.name.toLowerCase()} to give Gravitre a fuller picture of how your business runs.`
                  : "Every business area has a connected app."}
              </span>
              <Link className="io-btn" style={{ whiteSpace: "nowrap", textDecoration: "none" }} href={href}>
                {next ? next.cta : "Open Connectors"}
              </Link>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  )
}

// ---------------------------------------------------------------- at a glance

export function glanceValue(card: GlanceCard): string | null {
  if (card.value == null) return null
  if (card.id === "revenue") return formatMoneyCompact(card.value, card.currency)
  if (card.id === "hours") return card.value === 0 ? "0 hrs" : `≈ ${formatHours(card.value).replace(" h", " hrs")}`
  return card.value.toLocaleString("en-US")
}

export function AtAGlance({
  cards,
  loading,
  phrase,
  onOpen,
  children,
}: {
  cards: GlanceCard[]
  loading: boolean
  phrase: string
  /** Opens the records behind a card. */
  onOpen: (id: GlanceCard["id"]) => void
  /** The three cards below the results (knows, learning, attention). */
  children: ReactNode
}) {
  return (
    <section aria-labelledby="glance-h" style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <SectionHead
        id="glance-h"
        title="At a glance"
        sub={`${phrase.charAt(0).toUpperCase()}${phrase.slice(1)}'s results, and the three things worth knowing right now.`}
      />
      <div className="rs-grid" role="list" aria-label="This week's results">
        {cards.map((card) => {
          const look = GLANCE_LOOK[card.id]
          const value = glanceValue(card)
          return (
            <button key={card.id} type="button" role="listitem" className="rs-card io-rise" onClick={() => onOpen(card.id)}>
              <span data-io-muted style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, ...IO_TEXT.muted }}>
                <span className="rs-ico" style={{ background: look.bg, color: look.fg }}>
                  <Ico d={look.path} round />
                </span>
                {card.label}
              </span>
              <span className="rs-val">{value && !loading ? value : dash(loading)}</span>
              <span data-io-muted style={{ fontSize: 13, lineHeight: 1.45, ...IO_TEXT.muted }}>
                {card.hint}
              </span>
              <span className="rs-basis">
                {card.link.label}
                <Ico d={PATHS.arrow} size={12} width={2.2} />
              </span>
            </button>
          )
        })}
      </div>
      <div className="io-glance">{children}</div>
    </section>
  )
}

// ---------------------------------------------------------------- knows / learning / attention

export function KnowsCard({
  entities,
  relationships,
  apps,
  updatedAt,
  loading,
  onOpen,
}: {
  entities: number | null
  relationships: number | null
  apps: Connector[]
  updatedAt: string | null
  loading: boolean
  onOpen: () => void
}) {
  const shown = apps.slice(0, 4)
  const more = apps.length - shown.length
  const updated = updatedAt ? relativeTime(Date.parse(updatedAt)) : ""
  return (
    <article className="io-card io-gcard io-rise io-d1">
      <span className="io-eyebrow">What Gravitre knows</span>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <span className="io-big">{entities != null && !loading ? entities.toLocaleString("en-US") : dash(loading)}</span>
        <span data-io-muted style={{ fontSize: 15, ...IO_TEXT.muted }}>
          facts about your business
        </span>
      </div>
      <span data-io-muted style={{ fontSize: 14, lineHeight: 1.5, ...IO_TEXT.muted }}>
        {relationships != null
          ? `${relationships.toLocaleString("en-US")} links between customers, deals, people and terms`
          : "Customers, deals, tickets, policies and how they connect"}
        {apps.length > 0 ? `, from ${apps.length} connected ${apps.length === 1 ? "app" : "apps"}.` : ". No apps are connected yet."}
        {updated ? ` Updated ${updated}.` : ""}
      </span>
      {apps.length > 0 ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {shown.map((c) => (
            <span key={c.id} className="io-app">
              <AppDot vendor={String(c.vendor ?? "")} name={appName(c)} />
              {appName(c)}
            </span>
          ))}
          {more > 0 ? (
            <span className="io-app">
              <span className="io-appdot" style={{ background: "#8A8B85" }} aria-hidden>
                +
              </span>
              +{more} more
            </span>
          ) : null}
        </div>
      ) : null}
      <button type="button" className="io-link" onClick={onOpen}>
        View and correct knowledge
        <Ico d={PATHS.arrow} size={14} />
      </button>
    </article>
  )
}

export function LearningCard({
  newCount,
  phrase,
  top,
  topEvidence,
  pendingCount,
  loading,
  onOpen,
}: {
  newCount: number | null
  phrase: string
  top: PromotionCandidate | null
  topEvidence: string
  pendingCount: number
  loading: boolean
  onOpen: () => void
}) {
  return (
    <article className="io-card io-gcard io-rise io-d2">
      <span className="io-eyebrow">What it is learning</span>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <span className="io-big">{newCount != null && !loading ? newCount.toLocaleString("en-US") : dash(loading)}</span>
        <span data-io-muted style={{ fontSize: 15, ...IO_TEXT.muted }}>
          new {newCount === 1 ? "pattern" : "patterns"} {phrase}
        </span>
      </div>
      {top ? (
        <div className="io-quote">
          {String(top.content ?? "")}
          {topEvidence ? (
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10, fontSize: 12.5, color: "#0A6B47" }}>
              <span className="io-dot" style={{ background: "#19C37D" }} />
              {topEvidence}
            </div>
          ) : null}
        </div>
      ) : !loading ? (
        <div className="io-quote">
          Nothing new yet. Patterns show up here once an agent sees the same thing across several runs.
        </div>
      ) : null}
      <span data-io-muted style={{ fontSize: 13.5, lineHeight: 1.5, ...IO_TEXT.muted }}>
        Gravitre only starts using a pattern after someone on your team approves it.
      </span>
      <button type="button" className="io-link" onClick={onOpen}>
        {pendingCount > 0 ? `Review ${pendingCount} ${pendingCount === 1 ? "suggestion" : "suggestions"}` : "See what it is learning"}
        <Ico d={PATHS.arrow} size={14} />
      </button>
    </article>
  )
}

const ATTENTION_DOT: Record<AttentionItem["tone"], string> = {
  danger: "#A3333D",
  warning: "#E2A33A",
  live: "#19C37D",
}

export function AttentionCard({
  items,
  loading,
  onAction,
}: {
  items: AttentionItem[]
  loading: boolean
  /** Handles an item in place (returns true) instead of following its link. */
  onAction?: (item: AttentionItem) => boolean
}) {
  const shown = items.slice(0, 4)
  return (
    <article className="io-card io-gcard io-rise io-d3">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span className="io-eyebrow">Needs your attention</span>
        {!loading && items.length > 0 ? (
          <span
            style={{ fontSize: 12.5, fontWeight: 600, color: "#8A5A06", background: "#FBF1DC", borderRadius: 999, padding: "2px 9px" }}
          >
            {items.length} open
          </span>
        ) : null}
      </div>
      <div style={{ display: "flex", flexDirection: "column" }}>
        {loading ? (
          <div data-io-faint style={{ padding: "18px 0", fontSize: 14, ...IO_TEXT.faint }}>
            Checking…
          </div>
        ) : shown.length === 0 ? (
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "18px 0", fontSize: 14, color: "#0A6B47" }}>
            <span className="io-dot" style={{ background: "#19C37D" }} />
            You are all caught up.
          </div>
        ) : (
          shown.map((item) => (
            <div key={item.id} className="io-att">
              <span className="io-dot" style={{ background: ATTENTION_DOT[item.tone] }} />
              <span style={{ flex: 1, fontSize: 14, lineHeight: 1.4 }}>{item.text}</span>
              <Link
                className="io-btn"
                style={{ textDecoration: "none" }}
                href={item.href}
                onClick={(event) => {
                  if (onAction?.(item)) event.preventDefault()
                }}
              >
                {item.actionLabel}
              </Link>
            </div>
          ))
        )}
      </div>
    </article>
  )
}

// ---------------------------------------------------------------- how Gravitre thinks

const ART_FALLBACK = ["#FF7A59", "#03363D", "#EA4335", "#635BFF"]

/** Knowledge art: up to four connected apps feeding a fact stack, animated as in the design. */
function KnowledgeArt({ apps }: { apps: Connector[] }) {
  const rows = [22, 48, 74, 100]
  return (
    <div className="ax-art kx-art" aria-hidden>
      <svg viewBox="0 0 300 118" preserveAspectRatio="xMidYMid meet" style={{ width: "100%", height: "100%", display: "block" }}>
        <defs>
          <pattern id="kxDots" width="12" height="12" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r=".9" fill="#B9C6B8" />
          </pattern>
        </defs>
        <rect width="300" height="118" fill="url(#kxDots)" opacity=".55" />
        {rows.map((y, i) => {
          const app = apps[i]
          const color = app ? brandColor(String(app.vendor ?? "")) : ART_FALLBACK[i]
          const d = `M44 ${y} C 100 ${y}, 110 60, 166 60`
          return (
            <g key={`p${y}`}>
              <path d={d} fill="none" stroke="#CDEBDC" strokeWidth="1.3" />
              <path className={`kx-pkt kx-p${i}`} d={d} fill="none" stroke={color} strokeWidth="2.6" strokeLinecap="round" />
            </g>
          )
        })}
        {rows.map((y, i) => {
          const app = apps[i]
          const key = app ? vendorKey(String(app.vendor ?? "")) : ""
          return (
            <g key={`a${y}`} className={`kx-app kx-a${i}`}>
              <circle cx="30" cy={y} r="11" fill="#FFFFFF" stroke="#E4E4DF" />
              {app && LOGOS.has(key) ? (
                <image href={`/connector-logos/${key}.svg`} x="23.125" y={y - 6.875} width="13.75" height="13.75" />
              ) : app ? (
                <text x="30" y={y + 3.6} textAnchor="middle" fontSize="10" fontWeight="700" fill={brandColor(key)}>
                  {appName(app).charAt(0).toUpperCase()}
                </text>
              ) : (
                <circle cx="30" cy={y} r="3" fill="#CBCBC3" />
              )}
            </g>
          )
        })}
        <g className="kx-stack">
          <rect x="182" y="26" width="104" height="80" rx="12" fill="#FFFFFF" opacity=".55" transform="translate(8 -8)" />
          <rect x="180" y="20" width="104" height="80" rx="12" fill="#FFFFFF" stroke="#E4E4DF" />
        </g>
        {[
          [36, 58],
          [52, 44],
          [68, 64],
          [84, 36],
        ].map(([y, w], i) => (
          <g key={`f${y}`} className={`kx-fact kx-f${i}`}>
            <circle cx="196" cy={y} r="2.6" fill="#19C37D" />
            <rect x="204" y={y - 2.5} width={w} height="5" rx="2.5" fill="#33342F" opacity=".7" />
          </g>
        ))}
        <g className="kx-sync">
          <circle cx="276" cy="20" r="9" fill="#0B8A5C" />
          <path
            className="kx-spin"
            d="M272 19.5a4.2 4.2 0 0 1 7.4-2.4M280 20.5a4.2 4.2 0 0 1-7.4 2.4M279.6 14.6v2.8h-2.8M272.4 25.4v-2.8h2.8"
            fill="none"
            stroke="#FFFFFF"
            strokeWidth="1.3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </g>
      </svg>
    </div>
  )
}

/** Actions art: three checked rows feeding a rising chart, animated as in the design. */
function ActionsArt() {
  const rows: Array<[number, number, number, string]> = [
    [12, 74, 52, "#DDF3E8"],
    [46, 60, 70, "#EEF2FF"],
    [80, 82, 44, "#FBF1DC"],
  ]
  return (
    <div className="ax-art" aria-hidden>
      <svg viewBox="0 0 300 118" preserveAspectRatio="xMidYMid meet" style={{ width: "100%", height: "100%", display: "block" }}>
        <defs>
          <linearGradient id="axArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#19C37D" stopOpacity=".28" />
            <stop offset="1" stopColor="#19C37D" stopOpacity="0" />
          </linearGradient>
          <pattern id="axDots" width="12" height="12" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r=".9" fill="#B9C6B8" />
          </pattern>
        </defs>
        <rect width="300" height="118" fill="url(#axDots)" opacity=".55" />
        {rows.map(([y, w1, w2, chip], i) => (
          <g key={y} className={`ax-row ax-r${i + 1}`}>
            <rect x="12" y={y} width="170" height="26" rx="8" fill="#FFFFFF" stroke="#E4E4DF" />
            <circle cx="27" cy={y + 13} r="7" fill="#EFEFEA" className="ax-dot" />
            <circle cx="27" cy={y + 13} r="7" fill="#19C37D" className="ax-fill" />
            <path
              d={`M23.5 ${y + 13.2}l2.4 2.4 4.6-4.8`}
              fill="none"
              stroke="#FFFFFF"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="ax-check"
            />
            <rect x="41" y={y + 7} width={w1} height="5" rx="2.5" fill="#33342F" opacity=".75" />
            <rect x="41" y={y + 15.5} width={w2} height="4" rx="2" fill="#CBCBC3" />
            <rect x="148" y={y + 8} width="26" height="10" rx="5" fill={chip} opacity=".9" />
          </g>
        ))}
        <g className="ax-link">
          <path d="M186 25 C 200 25, 200 60, 214 60" fill="none" stroke="#19C37D" strokeWidth="1.4" strokeDasharray="3 3" opacity=".6" />
          <path d="M186 93 C 200 93, 200 60, 214 60" fill="none" stroke="#19C37D" strokeWidth="1.4" strokeDasharray="3 3" opacity=".6" />
        </g>
        <g className="ax-chart">
          <rect x="214" y="14" width="76" height="90" rx="12" fill="#FFFFFF" stroke="#E4E4DF" />
          <path className="ax-area" d="M222 92 L234 84 L246 86 L258 72 L270 62 L282 42 L282 96 L222 96 Z" fill="url(#axArea)" />
          <path
            className="ax-line"
            d="M222 92 L234 84 L246 86 L258 72 L270 62 L282 42"
            fill="none"
            stroke="#0B8A5C"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle className="ax-halo" cx="282" cy="42" r="7" fill="#19C37D" opacity=".25" />
          <circle className="ax-pt" cx="282" cy="42" r="3.4" fill="#0B8A5C" />
          <rect x="222" y="22" width="30" height="5" rx="2.5" fill="#33342F" opacity=".7" />
        </g>
      </svg>
    </div>
  )
}

function count(n: number | null, one: string, many: string): string | null {
  if (n == null) return null
  return `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`
}

export function abilityStatus(ability: Ability): string {
  if (!ability.enabled) return "Turned off"
  const mode = ability.mode ?? "balanced"
  return `${mode.charAt(0).toUpperCase()}${mode.slice(1)}${mode === "balanced" ? " (recommended)" : ""}`
}

export function HowGravitreThinks({
  apps,
  entities,
  recommendations,
  actions,
  awaiting,
  summary,
  abilities,
  onOpenKnowledge,
  onOpenAbility,
  onSeeActivity,
}: {
  apps: Connector[]
  entities: number | null
  recommendations: number | null
  actions: number | null
  awaiting: number | null
  summary: string | null
  abilities: Ability[]
  onOpenKnowledge: () => void
  onOpenAbility: (ability: Ability) => void
  onSeeActivity: () => void
}) {
  const [open, setOpen] = useState(false)
  const knowledgeLine =
    entities != null
      ? `${entities.toLocaleString("en-US")} facts from ${apps.length} ${apps.length === 1 ? "app" : "apps"}, kept fresh automatically.`
      : apps.length > 0
        ? `Facts from ${apps.length} connected ${apps.length === 1 ? "app" : "apps"}, kept fresh automatically.`
        : "Connect an app and Gravitre starts learning how your business works."
  const actionParts = [
    count(recommendations, "recommendation", "recommendations"),
    actions != null ? `${actions.toLocaleString("en-US")} ${actions === 1 ? "action" : "actions"} taken` : null,
    awaiting != null ? `${awaiting.toLocaleString("en-US")} waiting for you` : null,
  ].filter(Boolean)
  return (
    <section aria-labelledby="think-h" style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <SectionHead
        id="think-h"
        title="How Gravitre thinks"
        sub="Your knowledge goes in, Gravitre reasons about it, and useful actions come out. Nothing is changed in your apps without the approvals you set."
      />
      <div className="io-card io-think">
        <div className="io-mesh" aria-hidden />
        <div className="io-grid" aria-hidden />
        <div className="io-flow">
          <div className="io-stage io-rise io-d1">
            <KnowledgeArt apps={apps} />
            <span className="io-eyebrow">Knowledge</span>
            <span style={{ fontSize: 17, fontWeight: 600 }}>Your connected data</span>
            <span data-io-muted style={{ fontSize: 14, lineHeight: 1.5, ...IO_TEXT.muted }}>
              {knowledgeLine}
            </span>
            <button type="button" className="io-link" style={{ fontSize: 13 }} onClick={onOpenKnowledge}>
              See what it knows
            </button>
          </div>
          <div className="io-pipe" aria-hidden>
            <span className="io-pulse" />
            <span className="io-pulse b" />
          </div>
          <div className="io-stage core io-rise io-d2">
            <span className="io-sicon">
              <Ico d={PATHS.sparks} size={20} width={1.8} />
            </span>
            <span className="io-eyebrow" style={{ color: "#19C37D" }}>
              Intelligence
            </span>
            <span style={{ fontSize: 17, fontWeight: 600 }}>Understands, predicts and explains</span>
            <span style={{ fontSize: 14, color: "#CBCBC3", lineHeight: 1.5 }}>
              Seven abilities work together on every question, using only what is relevant.
            </span>
            <button
              type="button"
              className={open ? "io-toggle open" : "io-toggle"}
              onClick={() => setOpen((v) => !v)}
              aria-expanded={open}
            >
              {open ? "Hide the seven abilities" : "See the seven abilities"}
              <Ico d={PATHS.chevron} />
            </button>
          </div>
          <div className="io-pipe" aria-hidden>
            <span className="io-pulse" />
            <span className="io-pulse b" />
          </div>
          <div className="io-stage io-rise io-d3">
            <ActionsArt />
            <span className="io-eyebrow">Actions</span>
            <span style={{ fontSize: 17, fontWeight: 600 }}>Recommendations and results</span>
            <span data-io-muted style={{ fontSize: 14, lineHeight: 1.5, ...IO_TEXT.muted }}>
              {actionParts.length > 0 ? `${actionParts.join(", ")}.` : "Recommendations and finished work show up here."}
            </span>
            <button type="button" className="io-link" style={{ fontSize: 13 }} onClick={onSeeActivity}>
              See the activity
            </button>
          </div>
        </div>
        {open ? (
          <div className="io-abil" style={{ position: "relative" }}>
            {abilities.map((ability, i) => (
              <button
                key={ability.id}
                type="button"
                className="io-ab"
                style={{ animationDelay: `${(i * 0.04).toFixed(2)}s` }}
                onClick={() => onOpenAbility(ability)}
              >
                <span className="io-abi">
                  <Ico d={ability.path} size={15} width={1.9} />
                </span>
                <span style={{ fontSize: 13.5, fontWeight: 600, lineHeight: 1.3 }}>{ability.label}</span>
                <span data-io-muted style={{ fontSize: 12, ...IO_TEXT.muted }}>
                  {abilityStatus(ability)}
                </span>
              </button>
            ))}
          </div>
        ) : null}
        {summary ? (
          <p data-io-body style={{ position: "relative", margin: "22px 0 0", fontSize: 14, ...IO_TEXT.body }}>
            {summary}
          </p>
        ) : null}
      </div>
    </section>
  )
}

// ---------------------------------------------------------------- recent insights and activity

export type SweepStep = { name: string; state: "done" | "on" | "wait" }
export type SweepView =
  | { status: "running"; pct: number; steps: SweepStep[] }
  | { status: "done"; text: string }
  | { status: "idle" }

export function RecentActivity({
  id,
  items,
  loading,
  filter,
  onFilter,
  sweep,
  newIds,
  onOpen,
  onSelect,
}: {
  id?: string
  items: FeedItem[]
  loading: boolean
  filter: FeedKind | "all"
  onFilter: (filter: FeedKind | "all") => void
  sweep: SweepView
  /** Items that appeared after the last "Analyze my business". */
  newIds: Set<string>
  onOpen: (item: FeedItem) => void
  /** The item under the pointer or focus becomes Ask Gravitre's context. */
  onSelect?: (item: FeedItem) => void
}) {
  const visible = filter === "all" ? items : items.filter((item) => item.kind === filter)
  const empty =
    filter === "all"
      ? "Nothing yet. As agents run and forecasts come in, what Gravitre noticed, did and learned shows up here."
      : `No ${FEED_FILTERS.find((f) => f.id === filter)?.label.toLowerCase()} yet.`
  return (
    <section id={id} aria-labelledby="feed-h" style={{ display: "flex", flexDirection: "column", gap: 18, scrollMarginTop: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 16, flexWrap: "wrap" }}>
        <SectionHead
          id="feed-h"
          title="Recent insights and activity"
          sub="What Gravitre noticed, did, and learned. Open any item for the details."
        />
        <div className="io-seg" role="tablist" aria-label="Filter activity">
          {FEED_FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              role="tab"
              aria-selected={filter === f.id}
              className={filter === f.id ? "on" : ""}
              onClick={() => onFilter(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>
      {sweep.status === "running" ? (
        <div className="sw-banner" role="status" aria-live="polite">
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>Analyzing your business</span>
            <span data-io-muted style={{ fontSize: 13, flex: 1, ...IO_TEXT.muted }}>
              Re-reading your connected apps, using only data you are allowed to see. New findings will appear here.
            </span>
            <span className="io-mono" data-io-muted style={{ fontSize: 12, ...IO_TEXT.muted }}>
              {sweep.pct}%
            </span>
          </div>
          <div className="sw-bar">
            <span style={{ width: `${Math.max(6, sweep.pct)}%` }} />
          </div>
          <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
            {sweep.steps.map((step) => (
              <span key={step.name} className="sw-app">
                <span className={step.state === "done" ? "sw-st ok" : step.state === "on" ? "sw-st on" : "sw-st"} />
                {step.name}
                <span data-io-faint style={IO_TEXT.faint}>
                  {step.state === "done" ? "Done" : step.state === "on" ? "Reading" : "Waiting"}
                </span>
              </span>
            ))}
          </div>
        </div>
      ) : null}
      {sweep.status === "done" ? (
        <div className="sw-done" role="status" style={{ marginTop: 0 }}>
          <span className="io-dot" style={{ background: "#19C37D" }} />
          <span style={{ flex: 1 }}>{sweep.text}</span>
        </div>
      ) : null}
      <div className="io-card io-feed" style={{ overflow: "hidden" }}>
        {sweep.status === "running" || (loading && items.length === 0) ? (
          <>
            <div className="sw-skel">
              <span className="sw-sk1" />
              <span className="sw-sk2" />
            </div>
            <div className="sw-skel">
              <span className="sw-sk1" />
              <span className="sw-sk2" />
            </div>
          </>
        ) : null}
        {!loading && visible.length === 0 && sweep.status !== "running" ? (
          <p data-io-muted style={{ margin: 0, padding: "22px 24px", fontSize: 14, ...IO_TEXT.muted }}>
            {empty}
          </p>
        ) : null}
        {visible.map((item) => {
          const k = KIND[item.kind]
          const when = relativeTime(item.at)
          const meta = [...item.meta, when].filter(Boolean).join(" · ")
          return (
            <button
              key={item.id}
              type="button"
              className="io-item"
              onClick={() => onOpen(item)}
              onPointerEnter={() => onSelect?.(item)}
              onFocus={() => onSelect?.(item)}
            >
              <span className="io-itile" style={{ background: k.bg, color: k.fg }}>
                <Ico d={k.path} size={19} width={1.8} round />
              </span>
              <span style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
                <span style={{ fontSize: 15, fontWeight: 600, lineHeight: 1.35 }}>
                  {item.title}
                  {newIds.has(item.id) ? <span className="sw-new">New</span> : null}
                </span>
                <span data-io-muted style={{ fontSize: 14, lineHeight: 1.5, ...IO_TEXT.muted }}>
                  {item.detail}
                </span>
                {item.suggestion ? (
                  <span className="io-fixpill">
                    <Ico d={PATHS.play} size={13} />
                    {item.suggestionLabel ?? "Suggested"}: {item.suggestion}
                  </span>
                ) : null}
                {meta ? (
                  <span data-io-faint style={{ fontSize: 12.5, ...IO_TEXT.faint }}>
                    {meta}
                  </span>
                ) : null}
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span className="io-kind" style={{ background: k.bg, color: k.fg }}>
                  {k.label}
                </span>
                <span className="io-btn">{item.actionLabel}</span>
              </span>
            </button>
          )
        })}
      </div>
    </section>
  )
}
