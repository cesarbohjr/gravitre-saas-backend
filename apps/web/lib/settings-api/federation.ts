/**
 * Federation and B2B page mapping (design p17). Pure helpers over the real
 * /api/federation lists: stat tiles, partner labels and per-tab copy.
 */
import type {
  FederationConnectorGrant,
  FederationDelegatedTask,
  FederationHandoff,
  FederationPartnership,
} from "@/types/api"

/** Partnership as served by GET /api/federation/partnerships (name when visible). */
export type FederationPartnershipRow = FederationPartnership & { partnerOrgName?: string | null }

export interface FederationStats {
  active: number
  pending: number
  openHandoffs: number
  total: number
}

export function federationStats(partnerships: FederationPartnership[], handoffs: FederationHandoff[]): FederationStats {
  return {
    active: partnerships.filter((p) => p.status === "active").length,
    pending: partnerships.filter((p) => p.status === "pending_partner").length,
    openHandoffs: handoffs.filter((h) => h.status === "pending_receiver" || h.status === "accepted").length,
    total: partnerships.length,
  }
}

export function partnerLabel(p: FederationPartnershipRow): string {
  const name = (p.partnerOrgName || "").trim()
  if (name) return name
  return p.partnerOrgId ? `Org ${p.partnerOrgId.slice(0, 8)}` : "Unknown org"
}

/** The partner invited us and is waiting on our consent. */
export function awaitsOurConsent(p: FederationPartnership, viewerOrgId: string | null | undefined): boolean {
  const me = p.currentOrgId || viewerOrgId || ""
  if (!me) return false
  return p.status === "pending_partner" && p.invitedByOrgId !== me
}

export type FederationTab = "handoffs" | "grants" | "tasks"

export const FEDERATION_TABS: Array<{
  id: FederationTab
  label: string
  emptyTitle: string
  emptyText: string
  cta: string
}> = [
  {
    id: "handoffs",
    label: "Handoffs",
    emptyTitle: "No handoffs yet",
    emptyText: "When an agent passes work to a partner org, each handoff and its status shows here.",
    cta: "Send handoff",
  },
  {
    id: "grants",
    label: "Connector grants",
    emptyTitle: "No connector grants",
    emptyText: "Share read access to a connector with a partner, scoped and time boxed.",
    cta: "Grant access",
  },
  {
    id: "tasks",
    label: "Delegated tasks",
    emptyTitle: "No delegated tasks",
    emptyText: "Tasks a partner asks your agents to do, waiting for your approval.",
    cta: "Delegate task",
  },
]

export type PillTone = "green" | "amber" | "red" | "blue" | "neutral"

export const PARTNERSHIP_STATUS: Record<string, { label: string; tone: PillTone }> = {
  active: { label: "Active", tone: "green" },
  pending_partner: { label: "Pending consent", tone: "amber" },
  rejected: { label: "Declined", tone: "neutral" },
  revoked: { label: "Revoked", tone: "red" },
}

export const HANDOFF_STATUS: Record<string, { label: string; tone: PillTone }> = {
  pending_receiver: { label: "Pending", tone: "amber" },
  accepted: { label: "Accepted", tone: "blue" },
  completed: { label: "Completed", tone: "green" },
  rejected: { label: "Declined", tone: "neutral" },
  failed: { label: "Failed", tone: "red" },
}

export const GRANT_STATUS: Record<string, { label: string; tone: PillTone }> = {
  pending: { label: "Pending", tone: "amber" },
  active: { label: "Active", tone: "green" },
  rejected: { label: "Declined", tone: "neutral" },
  revoked: { label: "Revoked", tone: "neutral" },
}

export const TASK_STATUS: Record<string, { label: string; tone: PillTone }> = {
  pending: { label: "Pending", tone: "amber" },
  accepted: { label: "Accepted", tone: "blue" },
  in_progress: { label: "In progress", tone: "blue" },
  completed: { label: "Completed", tone: "green" },
  rejected: { label: "Declined", tone: "neutral" },
  failed: { label: "Failed", tone: "red" },
  cancelled: { label: "Cancelled", tone: "neutral" },
}

export function statusOf(map: Record<string, { label: string; tone: PillTone }>, status: string) {
  return map[status] ?? { label: status ? status.replace(/_/g, " ") : "Unknown", tone: "neutral" as PillTone }
}

export function handoffTitle(h: FederationHandoff): string {
  const fromBriefing = typeof h.briefing?.title === "string" ? h.briefing.title.trim() : ""
  return fromBriefing || (h.message || "").trim() || "Agent handoff"
}

export function canRespondToHandoff(h: FederationHandoff, viewerOrgId: string | null | undefined): boolean {
  return h.status === "pending_receiver" && Boolean(viewerOrgId) && h.receiverOrgId === viewerOrgId
}

export function grantPermissions(g: FederationConnectorGrant, viewerOrgId: string | null | undefined) {
  const isGrantee = Boolean(viewerOrgId) && viewerOrgId === g.granteeOrgId
  const isGrantor = Boolean(viewerOrgId) && viewerOrgId === g.grantorOrgId
  return {
    canAccept: isGrantee && g.status === "pending",
    canReject: isGrantee && g.status === "pending",
    canRevoke: isGrantor && g.status === "active",
    direction: isGrantor ? ("outgoing" as const) : isGrantee ? ("incoming" as const) : ("unknown" as const),
  }
}

export function canRespondToTask(t: FederationDelegatedTask, viewerOrgId: string | null | undefined): boolean {
  return Boolean(viewerOrgId) && viewerOrgId === t.delegateOrgId && t.status === "pending"
}
