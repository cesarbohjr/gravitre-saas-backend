/**
 * Billing and plan page mapping (design p16). Pure functions over the real
 * /api/billing overview so the page never shows a number Stripe or the plan
 * catalog did not give us.
 */
import type { BillingOverview, BillingUsageResponse, Invoice, PaymentMethod } from "@/types/api"
import { planLimitsFor } from "@/lib/plan-limits"

export function formatMoney(cents: number | null | undefined, currency = "usd"): string | null {
  if (cents == null || !Number.isFinite(cents)) return null
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: currency.toUpperCase() }).format(cents / 100)
  } catch {
    return `$${(cents / 100).toFixed(2)}`
  }
}

/** "Price" + "/ month" from the live Stripe price on the subscription, else the catalog list price. */
export function planPriceLabel(input: {
  unitAmountCents?: number | null
  interval?: string | null
  catalogPrice?: string | null
  catalogMonthly?: boolean
}): { amount: string; period: string | null } | null {
  if (typeof input.unitAmountCents === "number" && Number.isFinite(input.unitAmountCents)) {
    const whole = input.unitAmountCents % 100 === 0
    const amount = whole
      ? new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(
          input.unitAmountCents / 100,
        )
      : formatMoney(input.unitAmountCents) ?? "$0"
    const interval = String(input.interval ?? "").toLowerCase()
    const period = interval.startsWith("year") || interval === "annual" ? "/ year" : interval ? "/ month" : null
    return { amount, period }
  }
  if (!input.catalogPrice) return null
  return { amount: input.catalogPrice, period: input.catalogMonthly ? "/ month" : null }
}

export type UsageTone = "green" | "amber" | "red"

export interface UsageTile {
  key: string
  label: string
  used: number
  /** Real allowance, or null when there is no cap (metered or not set). */
  limit: number | null
  unit: string
  note: string
  /** Overage text when the API reports one. */
  overage?: string
  pct: number | null
  tone: UsageTone
}

function positive(...values: Array<number | null | undefined>): number | null {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value) && value > 0) return value
  }
  return null
}

export function usageTone(pct: number | null): UsageTone {
  if (pct === null) return "green"
  if (pct >= 90) return "red"
  if (pct >= 70) return "amber"
  return "green"
}

function tile(
  key: string,
  label: string,
  used: number,
  limit: number | null,
  unit: string,
  note: string,
  overage?: string,
): UsageTile {
  const pct = limit ? Math.round((used / limit) * 100) : null
  return { key, label, used, limit, unit, note, overage, pct, tone: usageTone(pct) }
}

/**
 * Usage tiles for this period. A limit comes from the API's included amount,
 * then from the plan catalog (which mirrors public.billing_plans); when
 * neither has a positive allowance the tile is shown as metered, never as a
 * made-up cap.
 */
export function usageTiles(usage: BillingUsageResponse | undefined, planCode: string | null | undefined): UsageTile[] {
  if (!usage) return []
  const limits = planLimitsFor(usage.tier ?? planCode ?? undefined)
  const totals = usage.totals ?? ({} as BillingUsageResponse["totals"])
  const tiles: UsageTile[] = [
    tile(
      "workflow_runs",
      "Workflow runs",
      Number(totals.workflow_runs ?? 0),
      positive(usage.workflow_runs_included, limits.workflowRuns),
      "runs",
      "Included in your plan",
    ),
    tile(
      "ai_credits",
      "AI credits",
      Number(totals.ai_tokens ?? 0),
      positive(usage.ai_credits_included, limits.aiCredits),
      "credits",
      "Model tokens only, separate from research",
    ),
    tile(
      "outputs",
      "Outputs",
      Number(totals.outputs ?? 0),
      positive(usage.included_outputs, limits.outputs),
      "outputs",
      "Delivered work units",
      usage.overage_outputs
        ? `${usage.overage_outputs} over, billed at ${formatMoney(Math.round((usage.output_overage_rate_usd ?? limits.outputOverageUsd ?? 0) * 100)) ?? "the overage rate"} each`
        : undefined,
    ),
  ]
  if (usage.research_lookups_billing_visible) {
    tiles.push(
      tile(
        "research_lookups",
        "Research lookups",
        Number(totals.research_lookups ?? 0),
        positive(usage.included_research_lookups, limits.researchLookups),
        "lookups",
        "Live internet research calls",
        usage.overage_research_lookups ? `${usage.overage_research_lookups} over the included amount` : undefined,
      ),
    )
  }
  if (usage.voice_minutes_billing_visible) {
    tiles.push(
      tile(
        "voice_minutes",
        "Voice minutes",
        Number(totals.voice_minutes ?? 0),
        positive(usage.included_voice_minutes, limits.voiceMinutes),
        "min",
        "Live voice session minutes",
        usage.overage_voice_minutes
          ? `${usage.overage_voice_minutes} min over, billed at ${formatMoney(Math.round((usage.voice_minute_overage_rate_usd ?? 0.12) * 100))}/min`
          : undefined,
      ),
    )
  }
  tiles.push(tile("api_calls", "API calls", Number(totals.api_calls ?? 0), null, "calls", "Metered, no plan cap"))
  return tiles
}

/** Bar width: a sliver once anything is used, never past 100%. */
export function usageBarWidth(t: UsageTile): string {
  if (t.pct === null) return "0%"
  if (t.used <= 0) return "0%"
  return `${Math.min(100, Math.max(1, t.pct))}%`
}

export interface InvoiceRow {
  id: string
  label: string
  number: string
  amount: string
  status: string
  tone: "green" | "amber" | "red" | "neutral"
  downloadUrl: string | null
}

const INVOICE_TONES: Record<string, InvoiceRow["tone"]> = {
  paid: "green",
  open: "amber",
  draft: "neutral",
  void: "neutral",
  uncollectible: "red",
}

export function invoiceRows(invoices: Array<Invoice & { number?: string | null; hosted_invoice_url?: string | null }> | undefined): InvoiceRow[] {
  return (invoices ?? []).map((invoice) => {
    const when = invoice.period_start || invoice.created_at
    const date = when ? new Date(when) : null
    const label =
      date && !Number.isNaN(date.getTime())
        ? date.toLocaleDateString(undefined, { month: "long", year: "numeric" })
        : "Invoice"
    const status = String(invoice.status || "").toLowerCase()
    return {
      id: invoice.id,
      label,
      number: invoice.number || invoice.id,
      amount: formatMoney(invoice.amount_cents, invoice.currency) ?? "",
      status: status ? status.charAt(0).toUpperCase() + status.slice(1).replace(/_/g, " ") : "Unknown",
      tone: INVOICE_TONES[status] ?? "neutral",
      downloadUrl: invoice.pdf_url || invoice.hosted_invoice_url || null,
    }
  })
}

export type CardOnFile = PaymentMethod & { brand?: string | null; last4?: string | null }

/** The default card, else the only card on file; null when there is none. */
export function defaultPaymentMethod(methods: BillingOverview["payment_methods"] | undefined): CardOnFile | null {
  const list = (methods ?? []) as CardOnFile[]
  return list.find((m) => m.is_default) ?? list[0] ?? null
}

const BRANDS: Record<string, string> = {
  visa: "Visa",
  mastercard: "Mastercard",
  amex: "American Express",
  discover: "Discover",
  diners: "Diners Club",
  jcb: "JCB",
  unionpay: "UnionPay",
}

export function cardTitle(card: CardOnFile): string {
  const brand = card.brand ? BRANDS[card.brand.toLowerCase()] ?? card.brand : card.type === "card" ? "Card" : card.type
  return card.last4 ? `${brand} ending ${card.last4}` : brand
}

export function cardExpiry(card: CardOnFile): string | null {
  if (!card.exp_month || !card.exp_year) return null
  return `Expires ${String(card.exp_month).padStart(2, "0")}/${card.exp_year}`
}

export type BillingStatusTone = "green" | "blue" | "amber" | "neutral"

export function billingStatusMeta(status: string, loading: boolean): { label: string; tone: BillingStatusTone; live: boolean } {
  switch (status) {
    case "active":
      return { label: "Active", tone: "green", live: true }
    case "trialing":
      return { label: "Trial", tone: "blue", live: true }
    case "past_due":
      return { label: "Past due", tone: "amber", live: false }
    case "canceled":
      return { label: "Canceled", tone: "neutral", live: false }
    default:
      return { label: loading ? "Loading" : "Unavailable", tone: "neutral", live: false }
  }
}

/** Normalized subscription status: org_billing wins, "cancelled" spelled the Stripe way. */
export function subscriptionStatus(overview: BillingOverview | undefined): string {
  const raw = String(overview?.subscription?.status || overview?.billing_status || "unknown")
    .trim()
    .toLowerCase()
  return raw === "cancelled" ? "canceled" : raw || "unknown"
}

export function longDate(iso: string | null | undefined): string | null {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" })
}

export function shortDate(iso: string | null | undefined): string | null {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

/** Line under the plan name: when access renews, ends, or the trial ends. */
export function renewalLine(status: string, periodEnd: string | null | undefined, cancelAtPeriodEnd: boolean): string | null {
  const date = longDate(periodEnd)
  if (!date) return null
  if (status === "canceled" || cancelAtPeriodEnd) return `Access ends ${date}`
  if (status === "trialing") return `Trial ends ${date}`
  return `Renews ${date}`
}

export function autoRenewLine(on: boolean, periodEnd: string | null | undefined): string {
  const date = longDate(periodEnd)
  if (on) return date ? `Renews automatically on ${date}` : "Renews automatically at the end of each period"
  return date ? `Your plan ends on ${date}. Turn this back on any time before then.` : "Auto renew is off"
}
