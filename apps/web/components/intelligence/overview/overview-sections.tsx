"use client"

/**
 * Overview sections (Intelligence-Main design): data readiness, at a glance,
 * what Gravitre knows / is learning / needs you for, how Gravitre thinks, and
 * recent insights and activity. Presentational only; overview-model.ts turns
 * the engine's responses into these props.
 */
import { useState, type ReactNode } from "react"
import Link from "next/link"
import {
  ArrowRight,
  CaretDown,
  ChartLineUp,
  Check,
  Clock,
  CurrencyDollar,
  Lightbulb,
  Play,
  Sparkle,
} from "@phosphor-icons/react"
import { Button } from "@/components/ui/button"
import { CertaintyMarker } from "@/components/intelligence/impact/certainty"
import { formatHours, formatUsd } from "@/components/intelligence/impact/impact-model"
import {
  FEED_FILTERS,
  READINESS_TIERS,
  SEVEN_ABILITIES,
  appName,
  type AttentionItem,
  type DataReadiness,
  type FeedItem,
  type FeedKind,
  type GlanceCard,
} from "@/components/intelligence/overview/overview-model"
import type { PromotionCandidate } from "@/lib/api"
import type { Connector } from "@/types/api"
import { cn } from "@/lib/utils"

const CARD = "rounded-[18px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)]"
const EYEBROW = "font-mono text-[11px] uppercase tracking-[0.12em] text-[color:var(--g-text-muted)]"
const GREEN_LINK =
  "inline-flex items-center gap-1 text-[13px] font-medium text-[color:var(--g-brand-active)] hover:text-[color:var(--g-brand-hover)] hover:underline underline-offset-2 dark:text-[color:var(--g-brand)]"

function Dash({ loading }: { loading?: boolean }) {
  return <span className="text-[color:var(--g-text-muted)]">{loading ? "…" : "—"}</span>
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

// ---------------------------------------------------------------- data readiness

export function DataReadinessCard({
  readiness,
  loading,
  href,
}: {
  readiness: DataReadiness
  loading: boolean
  href: string
}) {
  const reached = READINESS_TIERS.findIndex((t) => t.id === readiness.tier)
  return (
    <section
      aria-labelledby="overview-readiness-heading"
      className={cn(CARD, "flex flex-col gap-5 p-5 sm:p-6 lg:flex-row lg:items-center lg:justify-between")}
    >
      <div className="min-w-0 max-w-xl">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="overview-readiness-heading" className="text-[15px] font-semibold text-[color:var(--g-text-primary)]">
            Data readiness
          </h2>
          {!loading ? (
            <span className="rounded-full bg-[color:var(--g-brand-soft)] px-2 py-0.5 text-[12px] font-medium text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]">
              {readiness.label}
            </span>
          ) : null}
        </div>
        <p className="mt-1.5 text-[13.5px] leading-relaxed text-[color:var(--g-text-secondary)]">
          {loading ? "Checking which apps Gravitre can read…" : readiness.summary}
        </p>
      </div>
      <div className="w-full shrink-0 lg:w-[360px]">
        <ol className="grid grid-cols-3 gap-1.5" aria-label={`Readiness: ${readiness.label}`}>
          {READINESS_TIERS.map((tier, i) => (
            <li key={tier.id} className="min-w-0">
              <span
                aria-hidden
                className={cn(
                  "block h-1 rounded-full",
                  !loading && i <= reached ? "bg-[color:var(--g-brand-active)] dark:bg-[color:var(--g-brand)]" : "bg-[color:var(--g-border-default)]",
                )}
              />
              <span
                className={cn(
                  "mt-2 block truncate text-[12px]",
                  !loading && i === reached
                    ? "font-semibold text-[color:var(--g-text-primary)]"
                    : "text-[color:var(--g-text-muted)]",
                )}
                aria-current={!loading && i === reached ? "step" : undefined}
              >
                {tier.label}
              </span>
            </li>
          ))}
        </ol>
        <div className="mt-2 text-right">
          <Link href={href} className={GREEN_LINK}>
            See what is ready
          </Link>
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------- at a glance

const GLANCE_ICON: Record<GlanceCard["id"], { icon: ReactNode; tile: string }> = {
  revenue: {
    icon: <CurrencyDollar className="h-3.5 w-3.5" weight="bold" aria-hidden />,
    tile: "bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]",
  },
  hours: {
    icon: <Clock className="h-3.5 w-3.5" weight="bold" aria-hidden />,
    tile: "bg-[color:var(--g-signal-soft)] text-[color:var(--g-signal)]",
  },
  resolved: {
    icon: <Check className="h-3.5 w-3.5" weight="bold" aria-hidden />,
    tile: "bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]",
  },
  approval: {
    icon: <Clock className="h-3.5 w-3.5" weight="bold" aria-hidden />,
    tile: "bg-[color:var(--g-approval-soft)] text-[color:var(--g-approval)]",
  },
}

function glanceValue(card: GlanceCard): string | null {
  if (card.value == null) return null
  if (card.id === "revenue") return formatUsd(card.value)
  if (card.id === "hours") return card.value === 0 ? "0 hrs" : `≈ ${formatHours(card.value).replace(" h", " hrs")}`
  return card.value.toLocaleString("en-US")
}

export function AtAGlance({ cards, loading, phrase }: { cards: GlanceCard[]; loading: boolean; phrase: string }) {
  return (
    <section aria-labelledby="overview-glance-heading" className="space-y-3">
      <div>
        <h2 id="overview-glance-heading" className="text-[17px] font-semibold text-[color:var(--g-text-primary)]">
          At a glance
        </h2>
        <p className="mt-0.5 text-[13px] text-[color:var(--g-text-secondary)]">
          Results {phrase}, and what is worth knowing right now.
        </p>
      </div>
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => {
          const value = glanceValue(card)
          const meta = GLANCE_ICON[card.id]
          return (
            <li key={card.id} className={cn(CARD, "flex min-h-[150px] flex-col gap-2 p-4")}>
              <span className="flex items-center justify-between gap-2 text-[12.5px] text-[color:var(--g-text-secondary)]">
                <span className="flex items-center gap-2">
                  <span className={cn("grid h-6 w-6 place-items-center rounded-[7px]", meta.tile)}>{meta.icon}</span>
                  {card.label}
                </span>
                <CertaintyMarker certainty={loading ? "none" : card.certainty} />
              </span>
              <span className="text-[28px] font-semibold leading-none tracking-[-0.02em] tabular-nums text-[color:var(--g-text-primary)]">
                {value && !loading ? value : <Dash loading={loading} />}
              </span>
              <span className="text-[12.5px] leading-snug text-[color:var(--g-text-secondary)]">{card.hint}</span>
              <Link href={card.link.href} className={cn(GREEN_LINK, "mt-auto text-[12.5px]")}>
                {card.link.label}
                <ArrowRight className="h-3 w-3" weight="bold" aria-hidden />
              </Link>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

// ---------------------------------------------------------------- knows / learning / attention

function AppChip({ connector }: { connector: Connector }) {
  const name = appName(connector)
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--g-border-default)] px-2 py-1 text-[12px] text-[color:var(--g-text-primary)]">
      <span
        aria-hidden
        className="grid h-4 w-4 place-items-center rounded-full bg-[color:var(--g-text-primary)] text-[9px] font-semibold text-[color:var(--g-surface-1)]"
      >
        {name.charAt(0).toUpperCase()}
      </span>
      {name}
    </span>
  )
}

export function KnowsCard({
  entities,
  relationships,
  apps,
  updatedAt,
  loading,
  href,
}: {
  entities: number | null
  relationships: number | null
  apps: Connector[]
  updatedAt: string | null
  loading: boolean
  href: string
}) {
  const shown = apps.slice(0, 4)
  const more = apps.length - shown.length
  const updated = updatedAt ? relativeTime(Date.parse(updatedAt)) : ""
  return (
    <section aria-labelledby="overview-knows-heading" className={cn(CARD, "flex flex-col p-5")}>
      <h3 id="overview-knows-heading" className={EYEBROW}>
        What Gravitre knows
      </h3>
      <p className="mt-3 flex flex-wrap items-baseline gap-x-2.5">
        <span className="text-[38px] font-semibold leading-none tracking-[-0.03em] tabular-nums text-[color:var(--g-text-primary)]">
          {entities != null && !loading ? entities.toLocaleString("en-US") : <Dash loading={loading} />}
        </span>
        <span className="text-[14px] text-[color:var(--g-text-secondary)]">things about your business</span>
      </p>
      <p className="mt-3 text-[13.5px] leading-relaxed text-[color:var(--g-text-secondary)]">
        {relationships != null ? `${relationships.toLocaleString("en-US")} links between them` : "Customers, deals, people and terms"}
        {apps.length > 0 ? `, from ${apps.length} connected ${apps.length === 1 ? "app" : "apps"}.` : ". No apps are connected yet."}
        {updated ? ` Updated ${updated}.` : ""}
      </p>
      {shown.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {shown.map((c) => (
            <AppChip key={c.id} connector={c} />
          ))}
          {more > 0 ? (
            <span className="inline-flex items-center rounded-full border border-[color:var(--g-border-default)] px-2 py-1 text-[12px] text-[color:var(--g-text-secondary)]">
              +{more} more
            </span>
          ) : null}
        </div>
      ) : null}
      <Link href={href} className={cn(GREEN_LINK, "mt-auto pt-5")}>
        View and correct knowledge
        <ArrowRight className="h-3 w-3" weight="bold" aria-hidden />
      </Link>
    </section>
  )
}

export function LearningCard({
  newCount,
  phrase,
  top,
  topEvidence,
  pendingCount,
  loading,
  href,
}: {
  newCount: number | null
  phrase: string
  top: PromotionCandidate | null
  topEvidence: string
  pendingCount: number
  loading: boolean
  href: string
}) {
  return (
    <section aria-labelledby="overview-learning-heading" className={cn(CARD, "flex flex-col p-5")}>
      <h3 id="overview-learning-heading" className={EYEBROW}>
        What it is learning
      </h3>
      <p className="mt-3 flex flex-wrap items-baseline gap-x-2.5">
        <span className="text-[38px] font-semibold leading-none tracking-[-0.03em] tabular-nums text-[color:var(--g-text-primary)]">
          {newCount != null && !loading ? newCount.toLocaleString("en-US") : <Dash loading={loading} />}
        </span>
        <span className="text-[14px] text-[color:var(--g-text-secondary)]">
          new {newCount === 1 ? "pattern" : "patterns"} {phrase}
        </span>
      </p>
      {top ? (
        <div className="mt-3 rounded-[12px] border border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-surface)] p-3.5">
          <p className="text-[13.5px] leading-snug text-[color:var(--g-text-primary)]">{String(top.content ?? "")}</p>
          {topEvidence ? (
            <p className="mt-2 flex items-center gap-1.5 text-[12px] text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]">
              <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-current" />
              {topEvidence}
            </p>
          ) : null}
        </div>
      ) : !loading ? (
        <p className="mt-3 rounded-[12px] border border-dashed border-[color:var(--g-border-strong)] p-3.5 text-[13px] text-[color:var(--g-text-secondary)]">
          Nothing new yet. Patterns show up here once an agent sees the same thing across several runs.
        </p>
      ) : null}
      <p className="mt-3 text-[12.5px] leading-snug text-[color:var(--g-text-secondary)]">
        Gravitre only starts using a pattern after someone on your team approves it.
      </p>
      <Link href={href} className={cn(GREEN_LINK, "mt-auto pt-5")}>
        {pendingCount > 0 ? `Review ${pendingCount} ${pendingCount === 1 ? "suggestion" : "suggestions"}` : "Open memory"}
        <ArrowRight className="h-3 w-3" weight="bold" aria-hidden />
      </Link>
    </section>
  )
}

const ATTENTION_DOT: Record<AttentionItem["tone"], string> = {
  danger: "bg-[color:var(--g-danger)]",
  warning: "bg-[color:var(--g-approval)]",
  live: "bg-[color:var(--g-brand)]",
}

export function AttentionCard({ items, loading }: { items: AttentionItem[]; loading: boolean }) {
  return (
    <section aria-labelledby="overview-attention-heading" className={cn(CARD, "flex flex-col p-5")}>
      <div className="flex items-center justify-between gap-2">
        <h3 id="overview-attention-heading" className={EYEBROW}>
          Needs your attention
        </h3>
        {!loading && items.length > 0 ? (
          <span className="rounded-full bg-[color:var(--g-approval-soft)] px-2 py-0.5 text-[11.5px] font-medium text-[color:var(--g-approval)]">
            {items.length} open
          </span>
        ) : null}
      </div>
      {loading ? (
        <p className="mt-4 text-[13px] text-[color:var(--g-text-muted)]">Checking…</p>
      ) : items.length === 0 ? (
        <p className="mt-4 text-[13.5px] leading-relaxed text-[color:var(--g-text-secondary)]">
          Nothing is waiting on you. Approvals, sign-ins and new patterns show up here.
        </p>
      ) : (
        <ul className="mt-2 divide-y divide-[color:var(--g-border-subtle)]">
          {items.slice(0, 4).map((item) => (
            <li key={item.id} className="flex items-center gap-3 py-3">
              <span aria-hidden className={cn("h-1.5 w-1.5 shrink-0 rounded-full", ATTENTION_DOT[item.tone])} />
              <span className="min-w-0 flex-1 text-[13.5px] leading-snug text-[color:var(--g-text-primary)]">{item.text}</span>
              <Button asChild variant="outline" size="sm" className="h-8 shrink-0 rounded-[9px] px-3 text-[12.5px]">
                <Link href={item.href}>{item.actionLabel}</Link>
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

// ---------------------------------------------------------------- how Gravitre thinks

function KnowledgeArt({ apps }: { apps: Connector[] }) {
  const letters = (apps.length > 0 ? apps.slice(0, 4).map(appName) : ["", "", "", ""]).map((n) => n.charAt(0).toUpperCase())
  const tones = ["#e8603c", "#141513", "#d94a3a", "#5b5bd6"]
  return (
    <svg viewBox="0 0 200 96" className="h-full w-full" aria-hidden>
      {letters.map((letter, i) => {
        const y = 16 + i * 21
        return (
          <g key={i}>
            <path d={`M30 ${y} C 70 ${y}, 90 48, 128 48`} fill="none" stroke="var(--g-brand)" strokeOpacity="0.35" strokeWidth="1.2" />
            <circle cx="22" cy={y} r="8" fill={apps[i] ? tones[i] : "var(--g-border-strong)"} />
            {letter ? (
              <text x="22" y={y + 3} textAnchor="middle" fontSize="8" fontWeight="600" fill="#fff">
                {letter}
              </text>
            ) : null}
          </g>
        )
      })}
      <rect x="128" y="22" width="58" height="52" rx="8" fill="var(--g-surface-1)" stroke="var(--g-border-default)" />
      <rect x="138" y="34" width="36" height="4" rx="2" fill="var(--g-text-primary)" opacity="0.7" />
      <rect x="138" y="44" width="28" height="4" rx="2" fill="var(--g-text-muted)" opacity="0.5" />
      <circle cx="134" cy="36" r="1.6" fill="var(--g-brand)" />
    </svg>
  )
}

function ActionsArt() {
  return (
    <svg viewBox="0 0 200 96" className="h-full w-full" aria-hidden>
      {[0, 1, 2].map((i) => {
        const y = 18 + i * 24
        return (
          <g key={i}>
            <circle cx="22" cy={y} r="6" fill="var(--g-brand)" />
            <path d={`M19 ${y} l2 2 l4 -4`} stroke="#fff" strokeWidth="1.4" fill="none" strokeLinecap="round" />
            <rect x="34" y={y - 2} width="56" height="4" rx="2" fill="var(--g-text-primary)" opacity="0.65" />
            <rect x="98" y={y - 3} width="24" height="6" rx="3" fill="var(--g-brand-soft)" />
          </g>
        )
      })}
      <path d="M126 18 C 140 18, 140 48, 152 48 M126 66 C 140 66, 140 48, 152 48" fill="none" stroke="var(--g-brand)" strokeOpacity="0.4" strokeDasharray="3 3" />
      <rect x="152" y="26" width="38" height="44" rx="7" fill="var(--g-surface-1)" stroke="var(--g-border-default)" />
      <rect x="160" y="36" width="20" height="4" rx="2" fill="var(--g-text-primary)" opacity="0.7" />
    </svg>
  )
}

function FlowArrow() {
  return (
    <span aria-hidden className="hidden items-center justify-center lg:flex">
      <span className="h-2 w-2 rounded-full bg-[color:var(--g-brand)]" />
      <span className="h-px w-8 bg-[color:var(--g-brand)] opacity-60" />
      <ArrowRight className="-ml-1 h-3 w-3 text-[color:var(--g-brand)]" weight="bold" />
    </span>
  )
}

export function HowGravitreThinks({
  apps,
  entities,
  recommendations,
  actions,
  awaiting,
  summary,
  routes,
}: {
  apps: Connector[]
  entities: number | null
  recommendations: number | null
  actions: number | null
  awaiting: number | null
  summary: string | null
  routes: { knowledge: string; activity: string }
}) {
  const [open, setOpen] = useState(false)
  const count = (value: number | null, one: string, many: string) =>
    value == null ? null : `${value.toLocaleString("en-US")} ${value === 1 ? one : many}`
  const actionLine = [
    count(recommendations, "recommendation", "recommendations"),
    count(actions, "action taken", "actions taken"),
    count(awaiting, "waiting for you", "waiting for you"),
  ].filter(Boolean)
  return (
    <section aria-labelledby="overview-thinks-heading" className="space-y-3">
      <div>
        <h2 id="overview-thinks-heading" className="text-[17px] font-semibold text-[color:var(--g-text-primary)]">
          How Gravitre thinks
        </h2>
        <p className="mt-0.5 text-[13px] text-[color:var(--g-text-secondary)]">
          Your knowledge goes in, Gravitre reasons about it, and useful actions come out. Nothing is changed in your apps
          without the approvals you set.
        </p>
      </div>
      <div className="rounded-[18px] border border-[color:var(--g-border-default)] bg-[linear-gradient(135deg,var(--g-brand-surface),var(--g-surface-2))] p-4 sm:p-7">
        <div className="grid grid-cols-1 items-stretch gap-4 lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_auto_minmax(0,1fr)] lg:gap-2">
          <article className="flex flex-col rounded-[14px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-4">
            <div className="h-24 rounded-[10px] bg-[color:var(--g-surface-2)] p-2">
              <KnowledgeArt apps={apps} />
            </div>
            <p className={cn(EYEBROW, "mt-4")}>Knowledge</p>
            <h3 className="mt-1 text-[15px] font-semibold text-[color:var(--g-text-primary)]">Your connected data</h3>
            <p className="mt-1 text-[13px] leading-relaxed text-[color:var(--g-text-secondary)]">
              {entities != null
                ? `${entities.toLocaleString("en-US")} things from ${apps.length} ${apps.length === 1 ? "app" : "apps"}, kept fresh as they sync.`
                : "What your connected apps tell Gravitre, kept fresh as they sync."}
            </p>
            <Link href={routes.knowledge} className={cn(GREEN_LINK, "mt-auto pt-3")}>
              See what it knows
            </Link>
          </article>
          <FlowArrow />
          <article className="flex flex-col rounded-[14px] bg-[color:var(--g-carbon,#141513)] p-4 text-white dark:border dark:border-[color:var(--g-border-default)]">
            <span className="grid h-8 w-8 place-items-center rounded-[9px] bg-white/10 text-[color:var(--g-brand)]">
              <Sparkle className="h-4 w-4" weight="fill" aria-hidden />
            </span>
            <p className="mt-4 font-mono text-[11px] uppercase tracking-[0.12em] text-[color:var(--g-brand)]">Intelligence</p>
            <h3 className="mt-1 text-[15px] font-semibold">Understands, predicts and explains</h3>
            <p className="mt-1 text-[13px] leading-relaxed text-white/70">
              Seven abilities work together on every question, using only what is relevant.
            </p>
            {open ? (
              <ul id="overview-seven-abilities" className="mt-3 space-y-1.5">
                {SEVEN_ABILITIES.map((ability) => (
                  <li key={ability.id} className="text-[12.5px] leading-snug text-white/80">
                    <span className="font-semibold text-white">{ability.label}.</span> {ability.detail}
                  </li>
                ))}
              </ul>
            ) : null}
            <button
              type="button"
              aria-expanded={open}
              aria-controls="overview-seven-abilities"
              onClick={() => setOpen((v) => !v)}
              className="mt-auto inline-flex w-fit items-center gap-1.5 self-start rounded-full border border-white/25 px-3 py-1.5 text-[12.5px] font-medium text-white hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]"
              style={{ marginTop: open ? 12 : undefined }}
            >
              {open ? "Hide the seven abilities" : "See the seven abilities"}
              <CaretDown className={cn("h-3 w-3 transition-transform", open && "rotate-180")} weight="bold" aria-hidden />
            </button>
          </article>
          <FlowArrow />
          <article className="flex flex-col rounded-[14px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-4">
            <div className="h-24 rounded-[10px] bg-[color:var(--g-surface-2)] p-2">
              <ActionsArt />
            </div>
            <p className={cn(EYEBROW, "mt-4")}>Actions</p>
            <h3 className="mt-1 text-[15px] font-semibold text-[color:var(--g-text-primary)]">Recommendations and results</h3>
            <p className="mt-1 text-[13px] leading-relaxed text-[color:var(--g-text-secondary)]">
              {actionLine.length > 0 ? `${actionLine.join(", ")}.` : "What Gravitre suggested, did and is waiting on."}
            </p>
            <Link href={routes.activity} className={cn(GREEN_LINK, "mt-auto pt-3")}>
              See the activity
            </Link>
          </article>
        </div>
        {summary ? <p className="mt-5 text-[13.5px] text-[color:var(--g-text-primary)]">{summary}</p> : null}
      </div>
    </section>
  )
}

// ---------------------------------------------------------------- recent insights and activity

const KIND_META: Record<FeedKind, { label: string; icon: ReactNode; tile: string; badge: string }> = {
  recommendation: {
    label: "Recommendation",
    icon: <Sparkle className="h-4 w-4" weight="bold" aria-hidden />,
    tile: "bg-[color:var(--g-brand-surface)] text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]",
    badge: "bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]",
  },
  action: {
    label: "Action",
    icon: <Check className="h-4 w-4" weight="bold" aria-hidden />,
    tile: "bg-[color:var(--g-signal-surface)] text-[color:var(--g-signal)]",
    badge: "bg-[color:var(--g-signal-soft)] text-[color:var(--g-signal)]",
  },
  insight: {
    label: "Insight",
    icon: <Lightbulb className="h-4 w-4" weight="bold" aria-hidden />,
    tile: "bg-[color:var(--g-approval-surface)] text-[color:var(--g-approval)]",
    badge: "bg-[color:var(--g-approval-soft)] text-[color:var(--g-approval)]",
  },
  outcome: {
    label: "Outcome",
    icon: <ChartLineUp className="h-4 w-4" weight="bold" aria-hidden />,
    tile: "bg-[color:var(--g-surface-2)] text-[color:var(--g-text-secondary)]",
    badge: "bg-[color:var(--g-surface-2)] text-[color:var(--g-text-secondary)]",
  },
}

export function RecentActivity({
  items,
  loading,
  onDismiss,
  onSelect,
  id,
}: {
  items: FeedItem[]
  loading: boolean
  onDismiss?: (cardId: string) => void
  onSelect?: (item: FeedItem) => void
  id?: string
}) {
  const [filter, setFilter] = useState<FeedKind | "all">("all")
  const shown = (filter === "all" ? items : items.filter((item) => item.kind === filter)).slice(0, 12)
  return (
    <section id={id} aria-labelledby="overview-feed-heading" className="scroll-mt-6 space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 id="overview-feed-heading" className="text-[17px] font-semibold text-[color:var(--g-text-primary)]">
            Recent insights and activity
          </h2>
          <p className="mt-0.5 text-[13px] text-[color:var(--g-text-secondary)]">
            What Gravitre noticed, did, and learned. Open any item for the details.
          </p>
        </div>
        <div
          role="tablist"
          aria-label="Filter activity"
          className="flex w-full gap-0.5 overflow-x-auto rounded-full bg-[color:var(--g-surface-2)] p-1 [scrollbar-width:none] sm:w-auto"
        >
          {FEED_FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              role="tab"
              aria-selected={filter === f.id}
              onClick={() => setFilter(f.id)}
              className={cn(
                "min-h-8 shrink-0 rounded-full px-3 text-[12.5px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                filter === f.id
                  ? "bg-[color:var(--g-surface-1)] text-[color:var(--g-text-primary)] shadow-sm"
                  : "text-[color:var(--g-text-secondary)] hover:text-[color:var(--g-text-primary)]",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>
      <div className={cn(CARD, "overflow-hidden")}>
        {loading && items.length === 0 ? (
          <p className="p-6 text-[13px] text-[color:var(--g-text-muted)]">Loading recent activity…</p>
        ) : shown.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-[14px] font-medium text-[color:var(--g-text-primary)]">
              {filter === "all" ? "Nothing here yet" : `No ${FEED_FILTERS.find((f) => f.id === filter)?.label.toLowerCase()} yet`}
            </p>
            <p className="mx-auto mt-1 max-w-md text-[13px] text-[color:var(--g-text-secondary)]">
              Forecasts, suggestions, agent actions and confirmed results appear here as your connected apps sync and
              agents run.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-[color:var(--g-border-subtle)]">
            {shown.map((item) => {
              const meta = KIND_META[item.kind]
              const when = relativeTime(item.at)
              return (
                <li
                  key={item.id}
                  className="flex gap-4 px-4 py-4 sm:px-5"
                  onPointerEnter={() => onSelect?.(item)}
                  onFocus={() => onSelect?.(item)}
                >
                  <span className={cn("mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-[10px]", meta.tile)}>
                    {meta.icon}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[14px] font-semibold leading-snug text-[color:var(--g-text-primary)]">{item.title}</p>
                    {item.detail ? (
                      <p className="mt-0.5 text-[13px] leading-relaxed text-[color:var(--g-text-secondary)]">{item.detail}</p>
                    ) : null}
                    {item.suggestion ? (
                      <span className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-[color:var(--g-brand-surface)] px-2.5 py-1 text-[12px] font-medium text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]">
                        <Play className="h-3 w-3" weight="fill" aria-hidden />
                        Suggested: {item.suggestion}
                      </span>
                    ) : null}
                    {item.meta.length > 0 || when ? (
                      <p className="mt-1.5 text-[12px] text-[color:var(--g-text-muted)]">
                        {[...item.meta, when].filter(Boolean).join(" · ")}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-2 sm:flex-row sm:items-center">
                    <span className={cn("hidden rounded-full px-2 py-0.5 text-[11.5px] font-medium sm:inline", meta.badge)}>
                      {meta.label}
                    </span>
                    <Button asChild variant="outline" size="sm" className="h-8 rounded-[9px] px-3 text-[12.5px]">
                      <Link href={item.href}>{item.actionLabel}</Link>
                    </Button>
                    {item.cardId && onDismiss ? (
                      <button
                        type="button"
                        onClick={() => onDismiss(item.cardId!)}
                        className="text-[12px] text-[color:var(--g-text-muted)] underline-offset-2 hover:text-[color:var(--g-text-primary)] hover:underline"
                      >
                        Dismiss
                      </button>
                    ) : null}
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </section>
  )
}
