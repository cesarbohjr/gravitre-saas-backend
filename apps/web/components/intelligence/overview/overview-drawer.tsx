"use client"

/**
 * The Overview's side panel, built to the 10-30 design: one drawer with four
 * views (a feed item, an ability, the records behind a result, and what
 * Gravitre knows). It slides in over a scrim, closes on the scrim, the close
 * button or Escape, and every control in it calls the real API:
 *
 * - item: "Gravitre can fix this with a play" (evidence recommendations →
 *   approval-governed Play handoff), inline share to Slack or email, "Was this
 *   useful?" feedback, and technical details.
 * - ability: the workspace's mode and, for the safe abilities, the on/off switch.
 * - evidence: the rows a number is based on and how it is measured.
 * - know: memories in use and waiting, with Fix (edit while waiting, or a
 *   reviewed correction once in use).
 */
import { useEffect, useMemo, useRef, useState } from "react"
import { createPortal } from "react-dom"
import Link from "next/link"
import useSWR from "swr"
import {
  ABILITY_MODES,
  type Ability,
  type FeedItem,
  type GlanceCard,
} from "@/components/intelligence/overview/overview-model"
import { EVIDENCE_FEED_PREFIX } from "@/components/intelligence/evidence-play-recommendations"
import { SHARE_OPTIONS_KEY } from "@/components/intelligence/overlays/share-finding-dialog"
import { toast } from "@/components/intelligence/overlays/toast"
import {
  GLANCE_LOOK,
  IO_TEXT,
  Ico,
  KIND,
  PATHS,
  abilityStatus,
  brandColor,
} from "@/components/intelligence/overview/overview-sections"
import {
  assistantApi,
  intelligenceFindingsApi,
  memoryPromotionApi,
  type IntelligenceAbilityMode,
  type IntelligenceAbilityName,
  type PlayListItem,
  type PromotionCandidate,
  type ShareFindingApp,
} from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { intelligenceEvidenceApi, type EvidenceRecommendation } from "@/lib/intelligence-evidence-api"
import "./overview.css"

export type OverviewDrawerState =
  | { type: "item"; item: FeedItem }
  | { type: "ability"; id: IntelligenceAbilityName }
  | { type: "evidence"; id: GlanceCard["id"] }
  | { type: "know"; view?: "all" | "waiting" }

export type EvidenceRow = { key: string; label: string; src: string; value: string; open?: () => void; href?: string }
export type EvidenceView = {
  label: string
  value: string
  unit: string
  summary: string
  method: string
  rows: EvidenceRow[]
  /** Shown when there are no rows yet. */
  empty: string
  link?: { label: string; href: string }
}

const STEP_DOT = { ok: "#19C37D", wait: "#E2A33A", off: "#CBCBC3" }

function sentence(text: string): string {
  const t = text.trim()
  return t && !/[.!?]$/.test(t) ? `${t}.` : t
}

function humanize(value: string): string {
  const text = value.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim()
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : ""
}

function initials(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part.charAt(0).toUpperCase())
      .join("") || "?"
  )
}

// ---------------------------------------------------------------- shell

export function OverviewDrawer({
  state,
  onClose,
  ...views
}: {
  state: OverviewDrawerState | null
  onClose: () => void
} & ViewProps) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  useEffect(() => {
    if (!state) return
    closeRef.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [state, onClose])
  if (!state || !mounted) return null

  const head = drawerHead(state, views)
  return createPortal(
    <div className="io-root io-portal">
      <div className="io-scrim" onClick={onClose} aria-hidden />
      <aside className="io-drawer" role="dialog" aria-modal="true" aria-labelledby="io-drawer-h">
        <div className="io-dhead">
          <span className="io-itile" style={{ background: head.bg, color: head.fg, width: 40, height: 40 }}>
            <Ico d={head.path} size={18} width={1.8} round />
          </span>
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4 }}>
            <span className="io-eyebrow">{head.kicker}</span>
            <h3 id="io-drawer-h" style={{ margin: 0, fontSize: 19, lineHeight: 1.3, fontWeight: 600 }}>
              {head.title}
            </h3>
          </div>
          <button ref={closeRef} type="button" className="io-close" onClick={onClose} aria-label="Close">
            <Ico d={PATHS.close} size={16} />
          </button>
        </div>
        <div className="io-dbody">
          {state.type === "item" ? <ItemView key={state.item.id} item={state.item} onClose={onClose} {...views} /> : null}
          {state.type === "ability" ? <AbilityView key={state.id} id={state.id} {...views} /> : null}
          {state.type === "evidence" ? <EvidenceViewBody view={views.evidence(state.id)} /> : null}
          {state.type === "know" ? <KnowView initial={state.view ?? "all"} {...views} /> : null}
        </div>
      </aside>
    </div>,
    document.body,
  )
}

type ViewProps = {
  isAdmin: boolean
  abilities: Ability[]
  savingAbility: IntelligenceAbilityName | null
  onAbilityChange: (id: IntelligenceAbilityName, patch: { mode: IntelligenceAbilityMode; enabled: boolean }) => void
  evidence: (id: GlanceCard["id"]) => EvidenceView
  recommendations: EvidenceRecommendation[]
  plays: PlayListItem[]
  onEvidenceChanged: () => void
  candidates: PromotionCandidate[] | null
  candidatesError: boolean
  onCandidatesChanged: () => void
  onDismissCard: (cardId: string) => Promise<void>
  /** Page in Gravitre a shared item links back to. */
  sharePath: (item: FeedItem) => string
}

function drawerHead(state: OverviewDrawerState, views: ViewProps) {
  if (state.type === "item") {
    const k = KIND[state.item.kind]
    return { kicker: k.label, title: state.item.title, bg: k.bg, fg: k.fg, path: k.path }
  }
  if (state.type === "ability") {
    const a = views.abilities.find((x) => x.id === state.id)
    return { kicker: "Ability", title: a?.label ?? "Ability", bg: "#F3FBF7", fg: "#0B8A5C", path: a?.path ?? PATHS.spark }
  }
  if (state.type === "evidence") {
    const look = GLANCE_LOOK[state.id]
    return { kicker: "This week", title: views.evidence(state.id).label, bg: look.bg, fg: look.fg, path: look.path }
  }
  return { kicker: "Knowledge", title: "What Gravitre knows", bg: "#F3FBF7", fg: "#0B8A5C", path: PATHS.know }
}

function Tech({ rows }: { rows: Array<[string, string]> }) {
  const [open, setOpen] = useState(false)
  if (rows.length === 0) return null
  return (
    <div className="io-tech">
      <button type="button" className={open ? "io-techbtn open" : "io-techbtn"} onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <Ico d={PATHS.chevron} />
        <span style={{ flex: 1 }}>Technical details</span>
        <span data-io-faint style={{ fontSize: 12, ...IO_TEXT.faint }}>
          For admins and analysts
        </span>
      </button>
      {open
        ? rows.map(([k, v]) => (
            <div key={k} className="io-trow">
              <span>{k}</span>
              <span className="io-mono" style={{ fontSize: 12, overflowWrap: "anywhere" }}>
                {v}
              </span>
            </div>
          ))
        : null}
    </div>
  )
}

function Summary({ text }: { text: string }) {
  return (
    <p data-io-body style={{ margin: 0, fontSize: 15, lineHeight: 1.6, ...IO_TEXT.body }}>
      {text}
    </p>
  )
}

function Done({ text }: { text: string }) {
  return (
    <div
      role="status"
      style={{ display: "flex", alignItems: "center", gap: 10, background: "#F3FBF7", borderRadius: 12, padding: "12px 14px", fontSize: 14, color: "#0A6B47" }}
    >
      <span className="io-dot" style={{ background: "#19C37D" }} />
      {text}
    </div>
  )
}

// ---------------------------------------------------------------- item

function openLabel(item: FeedItem): string {
  if (item.id.startsWith("forecast:")) return "Open in Forecasts"
  if (item.id.startsWith("learning:")) return "Open in Knowledge"
  if (item.id.startsWith("event:")) return item.kind === "action" ? "Open in Activity" : "Open in Reports"
  return "Open"
}

function ItemView({
  item,
  onClose,
  isAdmin,
  recommendations,
  plays,
  onEvidenceChanged,
  onDismissCard,
  sharePath,
}: { item: FeedItem; onClose: () => void } & ViewProps) {
  const recId = item.id.startsWith(EVIDENCE_FEED_PREFIX) ? item.id.slice(EVIDENCE_FEED_PREFIX.length) : null
  const rec = recId ? (recommendations.find((r) => r.id === recId) ?? null) : null
  const sources = rec
    ? [...new Set(rec.sources.map((s) => humanize(s.object_type)).filter(Boolean))]
    : (item.sources ?? [])
  const why = rec ? [rec.description].filter(Boolean) : (item.why ?? [])
  const [dismissing, setDismissing] = useState(false)
  return (
    <>
      <Summary text={item.detail} />
      {why.length > 0 && !(why.length === 1 && why[0] === item.detail) ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>Why Gravitre thinks this</span>
          {why.map((w) => (
            <div key={w} className="io-why">
              <span style={{ color: "#0B8A5C" }}>●</span>
              <span>{w}</span>
            </div>
          ))}
        </div>
      ) : null}
      {rec ? <FixSection rec={rec} plays={plays} isAdmin={isAdmin} onChanged={onEvidenceChanged} /> : null}
      {sources.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>What it looked at</span>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {sources.map((s) => (
              <span key={s} className="io-src">
                {s}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      {!rec ? (
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <Link className="io-btn green" style={{ minHeight: 40, textDecoration: "none" }} href={item.href}>
            {openLabel(item)}
          </Link>
          {item.cardId ? (
            <button
              type="button"
              className="io-btn"
              style={{ minHeight: 40 }}
              disabled={dismissing}
              onClick={() => {
                setDismissing(true)
                void onDismissCard(item.cardId!).then(onClose, () => setDismissing(false))
              }}
            >
              {dismissing ? "Dismissing…" : "Dismiss"}
            </button>
          ) : (
            <button type="button" className="io-btn" style={{ minHeight: 40 }} onClick={onClose}>
              Close
            </button>
          )}
        </div>
      ) : null}
      {item.kind === "insight" || item.kind === "recommendation" ? <SharePanel item={item} path={sharePath(item)} /> : null}
      <Feedback id={item.id} />
      <Tech
        rows={
          rec
            ? [
                ["Recommendation", rec.kind ? humanize(rec.kind) : "Evidence-backed"],
                ["Source records", String(rec.sources.length)],
                ["Advisory only", rec.advisory_only ? "Yes" : "No"],
                ["Approval required", rec.approval_required ? "Yes" : "No"],
                ["Business impact", rec.business_impact == null ? "Not measured" : String(rec.business_impact)],
                ["Outcome verified", rec.outcome_verified ? "Yes" : "Not yet"],
              ]
            : (item.tech ?? [])
        }
      />
    </>
  )
}

function playName(key: string, plays: PlayListItem[]): string {
  return plays.find((entry) => entry.play.key === key)?.play.name || humanize(key)
}

function FixSection({
  rec,
  plays,
  isAdmin,
  onChanged,
}: {
  rec: EvidenceRecommendation
  plays: PlayListItem[]
  isAdmin: boolean
  onChanged: () => void
}) {
  const key = rec.recommended_play_key
  const entry = plays.find((p) => p.play.key === key)
  const installationId = entry?.installation?.id
  const ready =
    Boolean(installationId) &&
    entry?.installation?.operatingMode === "ACT WITH APPROVAL" &&
    Boolean(entry?.readiness.act_with_approval_ready)
  const { data: lifecycle, mutate } = useSWR(["intelligence/evidence-handoffs", rec.id], () =>
    intelligenceEvidenceApi.evidenceRecommendationHandoffs(rec.id),
  )
  const [sending, setSending] = useState(false)
  const [failure, setFailure] = useState<string | null>(null)
  const latest = lifecycle?.handoffs?.[0] ?? null
  const outcomes = latest?.outcomes ?? []
  const phase: "proposed" | "setup" | "awaiting" | "tracking" | "error" = latest
    ? latest.status === "handoff_error"
      ? "error"
      : outcomes.length > 0
        ? "tracking"
        : "awaiting"
    : ready
      ? "proposed"
      : "setup"
  const name = playName(key, plays)
  const stateLabel = {
    proposed: "Proposed",
    setup: "Needs setup",
    awaiting: "Waiting for approval",
    tracking: "Running · tracking outcome",
    error: "Needs checking",
  }[phase]
  const tone = phase === "tracking" ? { fg: "#0A6B47", bg: "#DDF3E8" } : phase === "proposed" ? { fg: "#33342F", bg: "#EFEFEA" } : { fg: "#8A5A06", bg: "#FBF1DC" }
  const level = entry?.installation?.operatingMode ? `${humanize(entry.installation.operatingMode.toLowerCase())} level` : "Not installed"

  async function request() {
    if (!installationId || sending) return
    setSending(true)
    setFailure(null)
    try {
      await intelligenceEvidenceApi.runEvidenceRecommendation(rec.id, installationId)
      await mutate()
      onChanged()
      toast.success(`Sent ${name} for approval`, { description: "Nothing changes in your apps until someone approves it." })
    } catch (err) {
      setFailure(err instanceof Error ? err.message : "The play was not started. Nothing was changed.")
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="io-fix">
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span className="io-fixicon">
          <Ico d={PATHS.play} size={16} width={1.9} />
        </span>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
          <span style={{ fontSize: 12, color: "#0A6B47", fontWeight: 600 }}>Gravitre can fix this with a play</span>
          <span style={{ fontSize: 15, fontWeight: 600 }}>{name}</span>
        </div>
        <span className="gx-state" style={{ color: tone.fg, background: tone.bg }}>
          {stateLabel}
        </span>
      </div>
      <div className="gx-sec">
        <span className="gx-h">What Gravitre proposes</span>
        <span data-io-body style={{ fontSize: 14, lineHeight: 1.55, ...IO_TEXT.body }}>
          {sentence(entry?.play.objective || `Hands this finding to the ${name} play`)} It works from the{" "}
          {rec.sources.length} source {rec.sources.length === 1 ? "record" : "records"} behind this recommendation.
        </span>
      </div>
      <div className="gx-sec">
        <span className="gx-h">What it will change</span>
        <div className="gx-list">
          <div className="gx-row">
            <span className="gx-sys">Your apps</span>
            <span style={{ flex: 1 }}>Only the steps the play&apos;s approver signs off on</span>
          </div>
          <div className="gx-row">
            <span className="gx-sys keep">Not changed</span>
            <span style={{ flex: 1 }}>Anything, until the play&apos;s approval is granted</span>
          </div>
        </div>
      </div>
      <div className="gx-ap">
        <span className="gx-apic" style={{ background: rec.approval_required ? "#FBF1DC" : "#DDF3E8", color: rec.approval_required ? "#8A5A06" : "#0A6B47" }}>
          <Ico d={PATHS.shield} size={15} width={1.9} />
        </span>
        <span style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
          <span style={{ fontSize: 13.5, fontWeight: 600 }}>
            {phase === "tracking" ? "Approved" : rec.approval_required ? "Approval required" : "No approval needed"}
          </span>
          <span data-io-muted style={{ fontSize: 12.5, ...IO_TEXT.muted }}>
            Approvers set on the play. It can write to your apps, so a person signs off first.
          </span>
        </span>
        <span data-io-faint style={{ fontSize: 12, whiteSpace: "nowrap", ...IO_TEXT.faint }}>
          {level}
        </span>
      </div>
      {phase === "proposed" ? (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button type="button" className="io-btn green" style={{ minHeight: 38 }} disabled={!isAdmin || sending} onClick={() => void request()}>
            {sending ? "Sending…" : "Request approval"}
          </button>
          <Link className="io-btn" style={{ minHeight: 38, textDecoration: "none" }} href={APP_ROUTES.plays}>
            Open in Plays
          </Link>
        </div>
      ) : null}
      {phase === "proposed" && !isAdmin ? <div className="gx-note warn">Only an admin can send a play for approval.</div> : null}
      {phase === "setup" ? (
        <>
          <div className="gx-note warn">
            {entry?.installation
              ? `${name} is installed but not set to act with approval yet.`
              : `${name} isn't installed yet.`}{" "}
            Set it up in Plays before Gravitre can use it.
          </div>
          <div>
            <Link className="io-btn" style={{ minHeight: 38, textDecoration: "none" }} href={APP_ROUTES.plays}>
              Set up {name}
            </Link>
          </div>
        </>
      ) : null}
      {phase === "awaiting" ? (
        <>
          <div className="gx-note warn">Sent to the play&apos;s approvers. Nothing changes until they approve.</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Link className="io-btn green" style={{ minHeight: 36, textDecoration: "none" }} href={APP_ROUTES.approvals}>
              Open approvals
            </Link>
            <Link className="io-btn" style={{ minHeight: 36, textDecoration: "none" }} href={APP_ROUTES.plays}>
              Open in Plays
            </Link>
          </div>
        </>
      ) : null}
      {phase === "error" ? (
        <div className="gx-note warn">The handoff to {name} needs checking in Plays before it can be tried again.</div>
      ) : null}
      {phase === "tracking" ? (
        <div className="gx-sec">
          <span className="gx-h">Outcome</span>
          <div className="gx-list">
            {outcomes.map((o) => (
              <div key={o.outcomeId} className="gx-row">
                <span className="io-dot" style={{ background: o.verified ? STEP_DOT.ok : STEP_DOT.wait, marginTop: 6 }} />
                <span style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{ fontWeight: 600 }}>{o.verified ? "Confirmed in your apps" : "Waiting to be confirmed"}</span>
                  <span data-io-muted style={{ fontSize: 12.5, ...IO_TEXT.muted }}>
                    {humanize(o.verificationState)}
                  </span>
                </span>
              </div>
            ))}
          </div>
          <span data-io-muted style={{ fontSize: 12.5, ...IO_TEXT.muted }}>
            A play finishing is not counted as a business result until your apps confirm it.
          </span>
        </div>
      ) : null}
      {failure ? (
        <div className="gx-note warn" role="alert">
          {failure}
        </div>
      ) : null}
    </div>
  )
}

function SharePanel({ item, path }: { item: FeedItem; path: string }) {
  const [open, setOpen] = useState(false)
  const [shared, setShared] = useState<string | null>(null)
  const { data, error, mutate } = useSWR(open ? SHARE_OPTIONS_KEY : null, () => intelligenceFindingsApi.shareOptions(), {
    revalidateOnFocus: false,
  })
  const apps = useMemo(() => data?.apps ?? [], [data])
  const [appId, setAppId] = useState<ShareFindingApp["id"] | "">("")
  const [to, setTo] = useState("")
  const [sending, setSending] = useState(false)
  const [failure, setFailure] = useState<string | null>(null)
  useEffect(() => {
    if (apps.length && !apps.some((a) => a.id === appId)) setAppId(apps[0].id)
  }, [apps, appId])
  const app = apps.find((a) => a.id === appId) ?? null
  const [kind, targetId] = to.split(":") as ["c" | "p" | "", string | undefined]
  const toName =
    kind === "c" ? app?.channels.find((c) => c.id === targetId)?.name : kind === "p" ? app?.people.find((p) => p.id === targetId)?.name : undefined
  const unavailable = data?.unavailable ?? []
  const dest = (a: ShareFindingApp) =>
    !toName || a.id !== appId ? (a.id === "slack" ? "Channel or direct message" : "Email to a person in your organization") : a.id === "slack" ? (kind === "c" ? `${toName} channel` : `Direct message to ${toName}`) : `${toName} by email`
  const preview = `${toName ? `Hi ${kind === "c" ? "team" : toName.split(" ")[0]}, sharing this from Gravitre: ` : "Sharing this from Gravitre: "}${item.title}. Open in Gravitre for the details.`

  async function send() {
    if (!app || !targetId || !toName || sending) return
    setSending(true)
    setFailure(null)
    try {
      await intelligenceFindingsApi.share({
        app: app.id,
        channelId: kind === "c" ? targetId : null,
        personId: kind === "p" ? targetId : null,
        title: item.title,
        summary: item.detail,
        note: "",
        path,
        findingId: item.id,
      })
      setShared(`Shared with ${toName} in ${app.name} (${dest(app)}).`)
      setOpen(false)
    } catch (err) {
      setFailure(err instanceof Error ? err.message : "The finding was not shared. Try again.")
    } finally {
      setSending(false)
    }
  }

  if (shared) return <Done text={shared} />
  if (!open) {
    return (
      <div>
        <button type="button" className="io-btn" onClick={() => setOpen(true)}>
          <Ico d={PATHS.share} size={14} width={1.8} />
          Share with your team
        </button>
      </div>
    )
  }
  return (
    <div className="io-share">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 15, fontWeight: 600 }}>Share this</span>
        <span data-io-faint style={{ fontSize: 12, ...IO_TEXT.faint }}>
          Internal only
        </span>
      </div>
      {error ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <span data-io-muted style={{ fontSize: 13.5, ...IO_TEXT.muted }}>
            Gravitre couldn&apos;t load where you can share. Try again in a moment.
          </span>
          <div>
            <button type="button" className="io-btn" onClick={() => void mutate()}>
              Try again
            </button>
          </div>
        </div>
      ) : !data ? (
        <span data-io-muted style={{ fontSize: 13.5, ...IO_TEXT.muted }}>
          Loading the apps your team uses…
        </span>
      ) : apps.length === 0 ? (
        <span data-io-muted style={{ fontSize: 13.5, ...IO_TEXT.muted }}>
          Connect Slack, or turn on email delivery, to share findings with your team.{" "}
          <Link href={APP_ROUTES.connectors} className="io-link" style={{ display: "inline" }}>
            Open connectors
          </Link>
        </span>
      ) : (
        <>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <span className="io-lab">Send to</span>
            {app && app.channels.length > 0 ? (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {app.channels.slice(0, 8).map((c) => {
                  const on = to === `c:${c.id}`
                  return (
                    <button key={c.id} type="button" className={on ? "io-pick on" : "io-pick"} aria-pressed={on} onClick={() => setTo(`c:${c.id}`)}>
                      <Ico d={PATHS.team} size={13} width={1.9} />
                      {c.name}
                    </button>
                  )
                })}
              </div>
            ) : null}
            {app && app.people.length > 0 ? (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {app.people.slice(0, 8).map((p) => {
                  const on = to === `p:${p.id}`
                  return (
                    <button key={p.id} type="button" className={on ? "io-pick on" : "io-pick"} aria-pressed={on} onClick={() => setTo(`p:${p.id}`)}>
                      <span className="io-av">{initials(p.name)}</span>
                      {p.name}
                    </button>
                  )
                })}
              </div>
            ) : null}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <span className="io-lab">Using</span>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {apps.map((a) => {
                const on = a.id === appId
                const vendor = a.id === "slack" ? "slack" : "gmail"
                return (
                  <button
                    key={a.id}
                    type="button"
                    className={on ? "io-appopt on" : "io-appopt"}
                    aria-pressed={on}
                    onClick={() => {
                      if (a.id !== appId) setTo("")
                      setAppId(a.id)
                    }}
                  >
                    <span
                      className="io-appdot"
                      aria-hidden
                      style={{
                        width: 24,
                        height: 24,
                        background: `#FFFFFF url(/connector-logos/${vendor}.svg) center / 62% no-repeat`,
                        boxShadow: "inset 0 0 0 1px #E4E4DF",
                        color: brandColor(vendor),
                      }}
                    />
                    <span style={{ flex: 1, display: "flex", flexDirection: "column", gap: 1, textAlign: "left" }}>
                      <span style={{ fontSize: 14, fontWeight: 600 }}>{a.name}</span>
                      <span data-io-muted style={{ fontSize: 12.5, ...IO_TEXT.muted }}>
                        {dest(a)}
                      </span>
                    </span>
                    <span className="io-radio" />
                  </button>
                )
              })}
            </div>
            {unavailable.length > 0 ? (
              <span data-io-faint style={{ fontSize: 12.5, lineHeight: 1.5, ...IO_TEXT.faint }}>
                {unavailable.join(" and ")} {unavailable.length > 1 ? "are" : "is"} not connected, so{" "}
                {unavailable.length > 1 ? "they are" : "it is"} not shown. Connect apps your team uses in Connectors.
              </span>
            ) : null}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <span className="io-lab">Message</span>
            <div className="io-msg">{preview}</div>
          </div>
          {failure ? (
            <div className="gx-note warn" role="alert">
              {failure}
            </div>
          ) : null}
        </>
      )}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" className="io-btn green" style={{ minHeight: 38 }} disabled={!toName || !app || sending} onClick={() => void send()}>
          {sending ? "Sending…" : toName && app ? `Send to ${toName} in ${app.name}` : "Choose who to send to"}
        </button>
        <button type="button" className="io-btn" style={{ minHeight: 38 }} disabled={sending} onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </div>
  )
}

function Feedback({ id }: { id: string }) {
  const [vote, setVote] = useState<"up" | "down" | null>(null)
  function send(next: "up" | "down") {
    if (vote === next) return
    setVote(next)
    void assistantApi.recommendationFeedback({ recommendation_id: id, accepted: next === "up" }).catch(() => {
      setVote(null)
      toast.error("Your feedback wasn't saved. Try again in a moment.")
    })
  }
  return (
    <div data-io-muted style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13, ...IO_TEXT.muted }}>
      Was this useful?
      <button type="button" className={vote === "up" ? "io-thumb on" : "io-thumb"} onClick={() => send("up")} aria-label="Useful" aria-pressed={vote === "up"}>
        <Ico d={PATHS.thumb} size={15} width={1.8} />
      </button>
      <button
        type="button"
        className={vote === "down" ? "io-thumb on" : "io-thumb"}
        onClick={() => send("down")}
        aria-label="Not useful"
        aria-pressed={vote === "down"}
      >
        <Ico d={PATHS.thumb} size={15} width={1.8} style={{ transform: "rotate(180deg)" }} />
      </button>
      {vote ? <span style={{ color: "#0A6B47" }}>Thanks, Gravitre will use this.</span> : null}
    </div>
  )
}

// ---------------------------------------------------------------- ability

function AbilityView({
  id,
  abilities,
  isAdmin,
  savingAbility,
  onAbilityChange,
}: { id: IntelligenceAbilityName } & ViewProps) {
  const ability = abilities.find((a) => a.id === id)
  if (!ability) return null
  const mode = ability.mode ?? "balanced"
  const on = ability.enabled
  const saving = savingAbility === id
  const label = ABILITY_MODES.find((m) => m.id === mode)?.label ?? "Balanced"
  return (
    <>
      <Summary text={ability.detail} />
      <div className="io-quote">
        <span style={{ fontSize: 12.5, color: "#0A6B47", fontWeight: 600 }}>For example</span>
        <div style={{ marginTop: 6 }}>{ability.example}</div>
      </div>
      <div style={{ display: "flex", gap: 12 }}>
        <div className="io-stat">
          <div className="io-big" style={{ fontSize: 28 }}>
            —
          </div>
          <div data-io-muted style={{ fontSize: 13, marginTop: 4, ...IO_TEXT.muted }}>
            times used this week (not measured yet)
          </div>
        </div>
        <div className="io-stat">
          <div style={{ fontSize: 15, fontWeight: 600 }}>{on ? "On" : "Turned off"}</div>
          <div data-io-muted style={{ fontSize: 13, marginTop: 4, ...IO_TEXT.muted }}>
            {on ? "Used when a question needs it" : "Turn it on below whenever you like."}
          </div>
        </div>
      </div>
      <div className="ic-ctrl">
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>How it should behave</span>
            <span data-io-faint style={{ fontSize: 12.5, ...IO_TEXT.faint }}>
              Applies to your whole workspace · {isAdmin ? "admins only" : "only admins can change this"}
            </span>
          </div>
          {ability.canTurnOff ? (
            <button
              type="button"
              role="switch"
              aria-checked={on}
              aria-label={`${on ? "Turn off" : "Turn on"} ${ability.label}`}
              className={on ? "ic-sw on" : "ic-sw"}
              disabled={!isAdmin || saving}
              onClick={() => onAbilityChange(id, { mode, enabled: !on })}
            >
              <span />
            </button>
          ) : null}
        </div>
        <div className={ability.canTurnOff && !on ? "ic-seg off" : "ic-seg"} role="radiogroup" aria-label="Behavior level">
          {ABILITY_MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              role="radio"
              aria-checked={mode === m.id}
              className={mode === m.id ? "on" : ""}
              disabled={!on || !isAdmin || saving}
              onClick={() => {
                if (m.id !== mode) onAbilityChange(id, { mode: m.id, enabled: on })
              }}
            >
              {m.label}
            </button>
          ))}
        </div>
        <div className="ic-desc">
          <span style={{ fontSize: 13, fontWeight: 600 }}>{on ? `${label}${mode === "balanced" ? " (recommended)" : ""}` : "Turned off"}</span>
          <span>{on ? ability.modes[mode] : "Gravitre will not use this ability until you turn it back on."}</span>
        </div>
        <span data-io-faint style={{ fontSize: 12.5, lineHeight: 1.5, ...IO_TEXT.faint }}>
          {saving ? "Saving…" : ability.why}
        </span>
      </div>
      <Tech
        rows={[
          ["Capability id", ability.id],
          ["Setting", abilityStatus(ability)],
          ["Saved", ability.mode ? "Workspace setting" : "Default (nothing saved yet)"],
          ["This week", "Not measured yet"],
          ["Processing time", "Not measured yet"],
        ]}
      />
    </>
  )
}

// ---------------------------------------------------------------- evidence

function EvidenceViewBody({ view }: { view: EvidenceView }) {
  return (
    <>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <span className="rs-val" style={{ fontSize: 36 }}>
          {view.value}
        </span>
        <span data-io-muted style={{ fontSize: 14, ...IO_TEXT.muted }}>
          {view.unit}
        </span>
      </div>
      <Summary text={view.summary} />
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>What this is based on</span>
        {view.rows.length === 0 ? (
          <span data-io-muted style={{ fontSize: 14, ...IO_TEXT.muted }}>
            {view.empty}
          </span>
        ) : (
          <div className="rs-list">
            {view.rows.map((row) => {
              const body = (
                <>
                  <span style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
                    <span style={{ fontSize: 14, fontWeight: 600 }}>{row.label}</span>
                    <span data-io-faint style={{ fontSize: 12.5, ...IO_TEXT.faint }}>
                      {row.src}
                    </span>
                  </span>
                  <span style={{ fontSize: 14, fontWeight: 600, whiteSpace: "nowrap" }}>{row.value}</span>
                </>
              )
              return row.href ? (
                <a key={row.key} className="rs-row" href={row.href} target="_blank" rel="noreferrer" style={{ textDecoration: "none", color: "inherit" }}>
                  {body}
                </a>
              ) : (
                <button key={row.key} type="button" className="rs-row" onClick={row.open} disabled={!row.open}>
                  {body}
                </button>
              )
            })}
          </div>
        )}
      </div>
      <div className="ic-desc">
        <span style={{ fontSize: 13, fontWeight: 600 }}>How it is measured</span>
        <span>{view.method}</span>
      </div>
      {view.link ? (
        <div>
          <Link className="io-btn" style={{ textDecoration: "none" }} href={view.link.href}>
            {view.link.label}
          </Link>
        </div>
      ) : null}
    </>
  )
}

// ---------------------------------------------------------------- know

const IN_USE = new Set(["written", "approved", "auto_promoted"])
const WAITING = new Set(["pending_approval", "candidate"])

function shortDate(value: unknown): string {
  const at = Date.parse(String(value ?? ""))
  return Number.isFinite(at) ? new Date(at).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : ""
}

function KnowView({
  initial,
  isAdmin,
  candidates,
  candidatesError,
  onCandidatesChanged,
}: { initial: "all" | "waiting" } & ViewProps) {
  const [view, setView] = useState<string>(initial)
  const [query, setQuery] = useState("")
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState("")
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState<string | null>(null)
  const [sent, setSent] = useState<Record<string, true>>({})
  const [failure, setFailure] = useState<string | null>(null)

  const rows = useMemo(() => (candidates ?? []).filter((c) => String(c.content ?? "").trim()), [candidates])
  // Corrections waiting for review, by the memory they would replace.
  const corrections = useMemo(() => {
    const map = new Map<string, PromotionCandidate>()
    for (const c of rows) {
      const target = c.metadata && typeof c.metadata.corrects_candidate_id === "string" ? c.metadata.corrects_candidate_id : null
      if (target && WAITING.has(String(c.status))) map.set(target, c)
    }
    return map
  }, [rows])
  const facts = rows.filter((c) => (IN_USE.has(String(c.status)) || WAITING.has(String(c.status))) && !(c.source_table === "memory_correction" && WAITING.has(String(c.status))))
  const categories = [...new Set(facts.map((c) => String(c.memory_category ?? "").trim()).filter(Boolean))].slice(0, 5)
  const picks: Array<[string, string]> = [["all", "All"], ["waiting", "Waiting for review"], ...categories.map((c) => [c, humanize(c)] as [string, string])]
  const q = query.trim().toLowerCase()
  const shown = facts.filter((c) => {
    if (view === "waiting" && !WAITING.has(String(c.status)) && !corrections.has(c.id)) return false
    if (view !== "all" && view !== "waiting" && String(c.memory_category ?? "") !== view) return false
    return !q || String(c.content ?? "").toLowerCase().includes(q) || String(c.memory_category ?? "").toLowerCase().includes(q)
  })

  async function save(c: PromotionCandidate) {
    const text = draft.trim()
    if (!text || busy) return
    setBusy(c.id)
    setFailure(null)
    try {
      if (WAITING.has(String(c.status))) await memoryPromotionApi.edit(c.id, text)
      else await memoryPromotionApi.correct(c.id, text, reason)
      setSent((s) => ({ ...s, [c.id]: true }))
      setEditing(null)
      onCandidatesChanged()
    } catch (err) {
      setFailure(err instanceof Error ? err.message : "The fix wasn't sent. Try again.")
    } finally {
      setBusy(null)
    }
  }

  async function applyCorrection(original: PromotionCandidate, correction: PromotionCandidate) {
    if (busy) return
    setBusy(original.id)
    setFailure(null)
    try {
      await memoryPromotionApi.approve(correction.id)
      onCandidatesChanged()
      toast.success("Correction approved", { description: "Gravitre uses the corrected memory from now on. The old one is retired." })
    } catch (err) {
      setFailure(err instanceof Error ? err.message : "The correction wasn't approved. Try again.")
    } finally {
      setBusy(null)
    }
  }

  return (
    <>
      <p data-io-muted style={{ margin: 0, fontSize: 14, lineHeight: 1.6, ...IO_TEXT.muted }}>
        Here is what Gravitre has learned about how your business works. If something is wrong, fix it. An admin reviews
        changes before Gravitre uses them.
      </p>
      <label
        className="io-in"
        style={{ display: "flex", alignItems: "center", gap: 8, minHeight: 42, padding: "0 12px", color: "#8A8B85" }}
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
        <input
          aria-label="Search knowledge"
          placeholder="Search memories, terms or patterns"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ flex: 1, border: 0, outline: "none", font: "inherit", fontSize: 14, color: "inherit", background: "transparent" }}
        />
      </label>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {picks.map(([id, name]) => (
          <button key={id} type="button" className={view === id ? "io-acct on" : "io-acct"} onClick={() => setView(id)}>
            {name}
          </button>
        ))}
      </div>
      {failure ? (
        <div className="gx-note warn" role="alert">
          {failure}
        </div>
      ) : null}
      <div style={{ display: "flex", flexDirection: "column" }}>
        {!isAdmin ? (
          <span data-io-muted style={{ fontSize: 14, ...IO_TEXT.muted }}>
            Only admins can see and fix what Gravitre has learned. Ask an admin to review it.
          </span>
        ) : candidatesError ? (
          <span data-io-muted style={{ fontSize: 14, ...IO_TEXT.muted }}>
            Gravitre couldn&apos;t load its memories just now. Try again in a moment.
          </span>
        ) : candidates == null ? (
          <span data-io-faint style={{ fontSize: 14, ...IO_TEXT.faint }}>
            Loading…
          </span>
        ) : shown.length === 0 ? (
          <span data-io-muted style={{ fontSize: 14, ...IO_TEXT.muted }}>
            {facts.length === 0
              ? "Nothing learned yet. Memories show up here once agents see the same thing across several runs."
              : "Nothing matches."}
          </span>
        ) : (
          shown.map((c) => {
            const waiting = WAITING.has(String(c.status))
            const correction = corrections.get(c.id)
            const pending = Boolean(sent[c.id] || correction)
            const isEditing = editing === c.id
            const when = shortDate(c.updated_at ?? c.created_at)
            return (
              <div key={c.id} className="io-fact">
                <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                  <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 3, minWidth: 0 }}>
                    <span data-io-faint style={{ fontSize: 12.5, ...IO_TEXT.faint }}>
                      {humanize(String(c.memory_category || c.candidate_type || "Memory"))}
                    </span>
                    <span style={{ fontSize: 15, fontWeight: 600, overflowWrap: "anywhere" }}>{String(c.content)}</span>
                    <span data-io-faint style={{ fontSize: 12.5, ...IO_TEXT.faint }}>
                      {sent[c.id] ? "Sent for review just now" : [waiting ? "Waiting for review" : "In use", when].filter(Boolean).join(" · ")}
                    </span>
                  </div>
                  {pending && !waiting ? (
                    <span style={{ fontSize: 12, color: "#8A5A06", background: "#FBF1DC", borderRadius: 999, padding: "3px 10px", whiteSpace: "nowrap" }}>
                      Sent for review
                    </span>
                  ) : !isEditing ? (
                    <button
                      type="button"
                      className="io-btn"
                      onClick={() => {
                        setEditing(c.id)
                        setDraft(String(c.content ?? ""))
                        setReason("")
                      }}
                    >
                      Fix
                    </button>
                  ) : null}
                </div>
                {correction && !isEditing ? (
                  <div
                    style={{ display: "flex", alignItems: "center", gap: 10, background: "#FBF1DC", borderRadius: 12, padding: "10px 12px", fontSize: 13, color: "#33342F" }}
                  >
                    <span style={{ flex: 1 }}>Suggested fix: {String(correction.content)}</span>
                    <button type="button" className="io-btn" disabled={busy === c.id} onClick={() => void applyCorrection(c, correction)}>
                      Use this
                    </button>
                  </div>
                ) : null}
                {isEditing ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 4 }}>
                    <input className="io-in" aria-label="Correct value" value={draft} onChange={(e) => setDraft(e.target.value)} />
                    {!waiting ? (
                      <input
                        className="io-in"
                        aria-label="Why"
                        placeholder="Why is this wrong? (optional)"
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                      />
                    ) : null}
                    <div style={{ display: "flex", gap: 8 }}>
                      <button
                        type="button"
                        className="io-btn green"
                        disabled={!draft.trim() || draft.trim() === String(c.content ?? "").trim() || busy === c.id}
                        onClick={() => void save(c)}
                      >
                        {busy === c.id ? "Sending…" : waiting ? "Save wording" : "Send for review"}
                      </button>
                      <button type="button" className="io-btn" onClick={() => setEditing(null)}>
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            )
          })
        )}
      </div>
      <Link className="io-link" href={`${APP_ROUTES.learning}?view=memory`}>
        Open knowledge
        <Ico d={PATHS.arrow} size={14} />
      </Link>
    </>
  )
}
