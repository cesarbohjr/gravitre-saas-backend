/**
 * Plays page model: turns the /api/plays catalog (readiness the org has earned
 * plus the authority it actually switched on) into the tiers, filters and
 * side-pane facts the page shows. Pure functions, so the rules are testable.
 *
 * Two things stay separate on purpose:
 *  - tier: what the org turned on (installation.operatingMode), "off" until set up;
 *  - readiness: what the Play has earned from connectors, actions and signals.
 * A Play is never shown as acting because it could act.
 */
import type { PlayInstallation, PlayListItem, PlayOperatingMode } from "@/lib/api"

export type PlayTier = "off" | "observe" | "recommend" | "act"
export type PlayReadinessState = "ready" | "connector" | "setup"

export const TIER_ORDER: PlayTier[] = ["observe", "recommend", "act", "off"]

export const TIER_LABEL: Record<PlayTier, string> = {
  off: "Not on",
  observe: "Observe",
  recommend: "Recommend",
  act: "Act",
}

export const READINESS_LABEL: Record<PlayReadinessState, string> = {
  ready: "Ready",
  connector: "Needs a connector",
  setup: "Needs setup",
}

/** Outcome Pack departments; "" is the cross-department platform Plays. */
const DEPARTMENT_LABEL: Record<string, string> = {
  "": "Cross department",
  customer_success: "Customer success",
  finance: "Finance",
  growth: "Growth",
  marketing: "Marketing",
  msp: "Service desk",
  sales: "Sales",
  support: "Support",
  operations: "Operations",
}

const DEPARTMENT_ART: Record<string, string> = {
  customer_success: "/illustrations/roster-customer-success.svg",
  finance: "/illustrations/dept-finance.svg",
  growth: "/illustrations/roster-sales.svg",
  marketing: "/illustrations/dept-marketing.svg",
  msp: "/illustrations/dept-support.svg",
  sales: "/illustrations/dept-sales.svg",
  support: "/illustrations/dept-support.svg",
  operations: "/illustrations/dept-operations.svg",
}

export function departmentKey(item: PlayListItem): string {
  return String(item.play.department ?? "").trim().toLowerCase()
}

export function departmentLabel(key: string): string {
  if (key in DEPARTMENT_LABEL) return DEPARTMENT_LABEL[key]
  return key
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((word, index) => (index === 0 ? word.charAt(0).toUpperCase() + word.slice(1) : word))
    .join(" ")
}

export function departmentArt(key: string): string {
  return DEPARTMENT_ART[key] ?? "/illustrations/dept-operations.svg"
}

export function tierOfMode(mode: PlayOperatingMode | string | null | undefined): PlayTier {
  switch (String(mode ?? "").toUpperCase()) {
    case "OBSERVE":
      return "observe"
    case "RECOMMEND":
      return "recommend"
    case "ACT WITH APPROVAL":
    case "ACT WITHIN POLICY":
      return "act"
    default:
      return "off"
  }
}

const ON_STATUSES = new Set(["ready", "active"])

export function tierOf(item: PlayListItem): PlayTier {
  const installation = item.installation
  // Draft, paused and archived set-ups are not running, so they read as off.
  if (!installation || !ON_STATUSES.has(String(installation.status ?? "").toLowerCase())) return "off"
  return tierOfMode(installation.operatingMode)
}

type GroupLike = { status?: string; vendors?: string[] }

function connectorGroups(item: PlayListItem): GroupLike[] {
  const groups = (item.readiness as { connector_groups?: unknown }).connector_groups
  return Array.isArray(groups) ? (groups.filter((g) => g && typeof g === "object") as GroupLike[]) : []
}

export function readinessOf(item: PlayListItem): PlayReadinessState {
  if (item.readiness.observe_ready) return "ready"
  if (connectorGroups(item).some((group) => group.status !== "AVAILABLE")) return "connector"
  return "setup"
}

/** Connector groups as one entry each: the connected vendor if any, else the first option. */
export function connectorChips(item: PlayListItem): Array<{ vendor: string; ready: boolean }> {
  return connectorGroups(item).map((group) => {
    const vendors = Array.isArray(group.vendors) ? group.vendors : []
    const states = ((group as { alternatives?: Record<string, string> }).alternatives ?? {}) as Record<string, string>
    const connected = vendors.find((vendor) => states[vendor] === "AVAILABLE")
    return { vendor: connected ?? vendors[0] ?? "connector", ready: group.status === "AVAILABLE" }
  })
}

export type RungState = "earned" | "current" | "locked"

/** Observe / Recommend / Act as the side pane shows them. */
export function ladder(item: PlayListItem): Array<{ tier: Exclude<PlayTier, "off">; label: string; state: RungState }> {
  const current = tierOf(item)
  const earned = {
    observe: Boolean(item.readiness.observe_ready),
    recommend: Boolean(item.readiness.recommend_ready),
    act: Boolean(item.readiness.act_with_approval_ready),
  }
  return (["observe", "recommend", "act"] as const).map((tier) => ({
    tier,
    label: TIER_LABEL[tier],
    state: current === tier ? "current" : earned[tier] ? "earned" : "locked",
  }))
}

const NEXT_MODE: Record<PlayTier, { mode: PlayOperatingMode; tier: Exclude<PlayTier, "off">; label: string } | null> = {
  off: { mode: "OBSERVE", tier: "observe", label: "Turn on Observe" },
  observe: { mode: "RECOMMEND", tier: "recommend", label: "Grant Recommend" },
  recommend: { mode: "ACT WITH APPROVAL", tier: "act", label: "Grant Act" },
  act: null,
}

/** The next authority this Play can be given, only when readiness has earned it. */
export function nextGrant(item: PlayListItem): { mode: PlayOperatingMode; tier: Exclude<PlayTier, "off">; label: string } | null {
  const next = NEXT_MODE[tierOf(item)]
  if (!next) return null
  const earned =
    next.tier === "observe"
      ? item.readiness.observe_ready
      : next.tier === "recommend"
        ? item.readiness.recommend_ready
        : item.readiness.act_with_approval_ready
  return earned ? next : null
}

export function setupHref(readiness: { blockers?: string[] }): string {
  const blockers = (readiness.blockers ?? []).join(" ").toLowerCase()
  if (blockers.includes("connector")) return "/connectors"
  if (blockers.includes("workflow")) return "/workflows"
  return "/connectors"
}

export type PlayFilters = {
  query: string
  department: string // "all" or a department key
  readiness: "all" | PlayReadinessState
  tier: "all" | PlayTier
}

export function filterPlays(items: PlayListItem[], filters: PlayFilters): PlayListItem[] {
  const q = filters.query.trim().toLowerCase()
  return items.filter((item) => {
    if (filters.department !== "all" && departmentKey(item) !== filters.department) return false
    if (filters.readiness !== "all" && readinessOf(item) !== filters.readiness) return false
    if (filters.tier !== "all" && tierOf(item) !== filters.tier) return false
    if (!q) return true
    const haystack = [
      item.play.name,
      item.play.objective,
      departmentLabel(departmentKey(item)),
      ...connectorChips(item).map((chip) => chip.vendor),
    ]
      .join(" ")
      .toLowerCase()
    return haystack.includes(q)
  })
}

export type PlaySummary = {
  total: number
  observeReady: number
  readyToTurnOn: number
  needsConnector: number
  tiers: Record<PlayTier, number>
}

export function summarize(items: PlayListItem[]): PlaySummary {
  const tiers: Record<PlayTier, number> = { off: 0, observe: 0, recommend: 0, act: 0 }
  let observeReady = 0
  let readyToTurnOn = 0
  let needsConnector = 0
  for (const item of items) {
    const tier = tierOf(item)
    const readiness = readinessOf(item)
    tiers[tier] += 1
    if (readiness === "ready") observeReady += 1
    if (readiness === "ready" && tier === "off") readyToTurnOn += 1
    if (readiness === "connector") needsConnector += 1
  }
  return { total: items.length, observeReady, readyToTurnOn, needsConnector, tiers }
}

/** Whole percent of all plays, never rounding a non-zero share down to 0%. */
export function shareOf(count: number, total: number): number {
  if (!total || !count) return 0
  return Math.max(1, Math.round((count / total) * 100))
}

export function installationBody(item: PlayListItem, mode: PlayOperatingMode, installation?: PlayInstallation | null) {
  return {
    playVersion: item.play.version,
    operatingMode: mode,
    goalId: installation?.goalId ?? null,
    // Granting authority switches the Play on: an active set-up stays active, anything else becomes ready.
    status: installation?.status === "active" ? "active" : "ready",
  }
}
