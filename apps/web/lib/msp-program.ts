/**
 * MSP partner program client.
 *
 * The model: an MSP pays Gravitre the wholesale price for each client workspace
 * and bills the client its own price. The difference is the MSP's margin.
 * Every request is authorized by FastAPI against the caller's role in the
 * right workspace (MSP owner/admin, or the client's owner for approvals).
 */
import { apiFetch } from "@/lib/fetcher"

export type MspPlanCode = "node" | "control" | "command"
export type MspInterval = "month" | "year"
export type MspClientStatus = "pending_client_approval" | "active" | "detached"
export type MspAccessLevel = "full" | "health_only"
export type WholesaleStatus = "not_configured" | "partial" | "ready"

export const MSP_PLAN_OPTIONS: { code: MspPlanCode; name: string }[] = [
  { code: "node", name: "Node" },
  { code: "control", name: "Control" },
  { code: "command", name: "Command" },
]

export { MSP_DOCS_HREF, MSP_EARNING_COPY, MSP_PRICING_HREF } from "@/lib/msp-program-copy"

export interface WholesalePrice {
  monthly_cents: number
  currency: string
}

export interface WholesaleSetup {
  status: WholesaleStatus
  stripe_configured: boolean
  configured_tiers: MspPlanCode[]
  message: string | null
  prices?: Partial<Record<MspPlanCode, WholesalePrice | null>>
}

export interface MspPerson {
  user_id: string
  role: string
  name: string | null
  email: string | null
}

export interface MspOverview {
  org: { id: string; name: string | null; account_type: "standard" | "msp" }
  role: string
  is_msp: boolean
  can_manage: boolean
  can_enroll: boolean
  wholesale: WholesaleSetup
  billing_account: { status: string; current_period_end: string | null; cancel_at_period_end: boolean } | null
  managed_by: {
    relationship_id: string
    msp_org_id: string
    msp_name: string
    plan_code: MspPlanCode
    plan_name: string
    access_level: MspAccessLevel
    can_detach: boolean
  } | null
  pending_request: {
    relationship_id: string
    msp_org_id: string
    msp_name: string
    plan_code: MspPlanCode
    plan_name: string
    requested_at: string | null
    msp_members: MspPerson[]
    own_subscription_conflict: string | null
  } | null
}

export interface MspUsage {
  ai_credits?: number
  workflow_runs?: number
  operator_usage?: number
  rag_usage?: number
}

export interface MspClientRow {
  id: string
  client_org_id: string
  name: string | null
  plan_code: MspPlanCode
  plan_name: string
  list_price_usd: number | null
  status: MspClientStatus
  origin: "created" | "linked"
  access_level: MspAccessLevel | null
  resale_price_cents: number | null
  resale_interval: MspInterval
  resale_currency: string
  resale_monthly_cents: number | null
  wholesale_monthly_cents: number | null
  margin_monthly_cents: number | null
  approved_at: string | null
  created_at: string | null
  can_open: boolean
  members: number | null
  usage: MspUsage | null
  health: { label: "healthy" | "attention"; org_status: string; billing_status: string } | null
}

export interface MspClientList {
  clients: MspClientRow[]
  totals: {
    wholesale_monthly_cents: number
    resale_monthly_cents: number
    margin_monthly_cents: number
    active_clients: number
    complete: boolean
  }
  period: { start: string; end: string }
  wholesale: WholesaleSetup
  truncated: boolean
}

export type BillingSyncStatus = "synced" | "checkout_required" | "not_configured" | "no_change" | "error"

export interface BillingSync {
  status: BillingSyncStatus
  quantities?: Record<MspPlanCode, number>
  message?: string
}

export interface BilledBy {
  msp_org_id: string
  msp_name: string
  plan_code: MspPlanCode | null
  plan_name: string
  billing_status: string | null
}

export class MspRequestError extends Error {
  constructor(message: string, readonly status: number, readonly code?: string) {
    super(message)
    this.name = "MspRequestError"
  }
}

function detailMessage(payload: unknown, status: number): { message: string; code?: string } {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail
    if (typeof detail === "string") return { message: detail }
    if (detail && typeof detail === "object") {
      const d = detail as { message?: unknown; code?: unknown }
      if (typeof d.message === "string") return { message: d.message, code: typeof d.code === "string" ? d.code : undefined }
    }
  }
  return { message: `Request failed (${status})` }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await apiFetch(path, options)
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    const { message, code } = detailMessage(payload, response.status)
    throw new MspRequestError(message, response.status, code)
  }
  return response.json() as Promise<T>
}

function json(method: string, body?: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  }
}

const BASE = "/api/msp/program"

export const mspProgramApi = {
  overview: () => request<MspOverview>(BASE),
  billedBy: () => request<{ billed_by: BilledBy | null }>(`${BASE}/billed-by`),
  enroll: () => request<{ account_type: "msp"; changed: boolean }>(`${BASE}/enroll`, json("POST")),
  listClients: () => request<MspClientList>(`${BASE}/clients`),
  createClient: (body: { name: string; plan_code: MspPlanCode; resale_price_cents: number | null; resale_interval: MspInterval }) =>
    request<{ client: { id: string; client_org_id: string; name: string; status: MspClientStatus }; billing: BillingSync }>(
      `${BASE}/clients`,
      json("POST", body),
    ),
  linkClient: (body: { client_org_id: string; plan_code: MspPlanCode; resale_price_cents: number | null; resale_interval: MspInterval }) =>
    request<{ client: { id: string; client_org_id: string; status: MspClientStatus } }>(`${BASE}/clients/link`, json("POST", body)),
  updateClient: (
    id: string,
    body: { plan_code?: MspPlanCode; resale_price_cents?: number | null; resale_interval?: MspInterval; clear_resale_price?: boolean },
  ) => request<{ id: string; billing: BillingSync }>(`${BASE}/clients/${encodeURIComponent(id)}`, json("PATCH", body)),
  detach: (id: string) => request<{ id: string; status: "detached" }>(`${BASE}/clients/${encodeURIComponent(id)}/detach`, json("POST")),
  approve: (id: string, body: { access_level: MspAccessLevel; member_user_ids: string[] }) =>
    request<{ id: string; status: "active" }>(`${BASE}/requests/${encodeURIComponent(id)}/approve`, json("POST", body)),
  decline: (id: string) => request<{ id: string }>(`${BASE}/requests/${encodeURIComponent(id)}/decline`, json("POST")),
  startBilling: (interval: MspInterval = "month") => request<{ url: string }>(`${BASE}/billing/checkout`, json("POST", { interval })),
  syncBilling: () => request<BillingSync>(`${BASE}/billing/sync`, json("POST")),
  /** Raw CSV download through the authenticated fetch (keeps the org header). */
  statement: async (period?: string): Promise<{ blob: Blob; filename: string }> => {
    const query = period ? `?period=${encodeURIComponent(period)}` : ""
    const response = await apiFetch(`${BASE}/statement.csv${query}`)
    if (!response.ok) {
      const payload: unknown = await response.json().catch(() => null)
      const { message } = detailMessage(payload, response.status)
      throw new MspRequestError(message, response.status)
    }
    const disposition = response.headers.get("content-disposition") ?? ""
    const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "gravitre-rebilling.csv"
    return { blob: await response.blob(), filename }
  },
}

/** "$41.00" from cents; "Not available" stays the caller's choice for null. */
export function formatCents(cents: number | null | undefined, currency = "usd"): string | null {
  if (cents === null || cents === undefined) return null
  return new Intl.NumberFormat("en-US", { style: "currency", currency: currency.toUpperCase() }).format(cents / 100)
}

/** Dollars typed by a person ("120", "120.50", "$1,200") to cents, or null when blank/invalid. */
export function parseDollarsToCents(value: string): number | null {
  const cleaned = value.replace(/[$,\s]/g, "")
  if (!cleaned) return null
  if (!/^\d+(\.\d{0,2})?$/.test(cleaned)) return null
  return Math.round(Number(cleaned) * 100)
}

export function clientStatusLabel(status: MspClientStatus): string {
  if (status === "pending_client_approval") return "Waiting for approval"
  if (status === "active") return "Active"
  return "Detached"
}

export function accessLevelLabel(level: MspAccessLevel | null): string {
  if (level === "full") return "Full access"
  if (level === "health_only") return "Health only"
  return "Not decided yet"
}

export function personLabel(person: { name?: string | null; email?: string | null }, fallback = "Team member"): string {
  if (person.name && person.email) return `${person.name} (${person.email})`
  return person.name || person.email || fallback
}

/** What the partner's billing state means for the Clients page, in plain words. */
export function billingStateCopy(overview: Pick<MspOverview, "wholesale" | "billing_account">): {
  tone: "green" | "amber" | "red" | "white"
  title: string
  body: string
  action: "start" | null
} {
  if (overview.wholesale.status === "not_configured") {
    return {
      tone: "white",
      title: "Wholesale billing isn't set up yet",
      body: "You can add clients now. Gravitre will ask you to start billing once wholesale prices are available, and your clients keep a normal 7-day trial until then.",
      action: null,
    }
  }
  const status = overview.billing_account?.status ?? "none"
  if (status === "active" || status === "trialing") {
    return {
      tone: "green",
      title: "Wholesale billing is running",
      body: "Adding, removing or changing a client's plan updates your subscription right away, prorated.",
      action: null,
    }
  }
  if (status === "past_due") {
    return {
      tone: "red",
      title: "Your wholesale payment failed",
      body: "Your clients are blocked until the payment goes through. Update the card in Stripe to restore them.",
      action: null,
    }
  }
  if (status === "canceled") {
    return {
      tone: "amber",
      title: "Wholesale billing was cancelled",
      body: "Your clients lost access. Start billing again to restore them.",
      action: "start",
    }
  }
  return {
    tone: "amber",
    title: "Start wholesale billing",
    body: "One subscription covers all your clients. Until you start it, clients run on a 7-day trial.",
    action: "start",
  }
}
