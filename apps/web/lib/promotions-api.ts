import { apiFetch } from "@/lib/fetcher"
import type { CurrentPromotions, PromoValidation } from "@/lib/promotions"
import { normalizePromoCode } from "@/lib/promotions"

const INVALID: PromoValidation = { valid: false, summary: null, reason: "This promo code isn't valid or has expired." }

async function readDetail(response: Response): Promise<string | null> {
  const body = (await response.json().catch(() => null)) as { detail?: unknown } | null
  const detail = body?.detail
  if (typeof detail === "string") return detail
  if (detail && typeof detail === "object" && "message" in detail) return String((detail as { message: unknown }).message)
  return null
}

/** Public, rate-limited validation. Never throws; network errors read as "try again". */
export async function validatePromoCode(code: string, plan?: string | null): Promise<PromoValidation> {
  const normalized = normalizePromoCode(code)
  if (!normalized) return INVALID
  const params = new URLSearchParams({ code: normalized })
  if (plan) params.set("plan", plan)
  try {
    const response = await apiFetch(`/api/billing/promo-codes/validate?${params.toString()}`, { method: "GET" })
    if (response.status === 429) {
      return { valid: false, summary: null, reason: "Too many attempts. Try again in a minute." }
    }
    if (!response.ok) {
      return { valid: false, summary: null, reason: (await readDetail(response)) ?? "We couldn't check this code. Try again." }
    }
    return (await response.json()) as PromoValidation
  } catch {
    return { valid: false, summary: null, reason: "We couldn't check this code. Try again." }
  }
}

/** The signed-in org's founder offer and live Stripe discount. */
export async function fetchCurrentPromotions(): Promise<CurrentPromotions> {
  const response = await apiFetch("/api/billing/promotions/current", { method: "GET" })
  if (!response.ok) throw new Error((await readDetail(response)) ?? "Could not load promotions")
  return (await response.json()) as CurrentPromotions
}

export type AdminPromotionCode = {
  id: string
  code: string
  summary: string
  status: "active" | "inactive" | "expired" | "exhausted"
  percent_off: number | null
  amount_off_cents: number | null
  duration: "once" | "repeating" | "forever"
  duration_in_months: number | null
  max_redemptions: number | null
  times_redeemed: number
  expires_at: string | null
  first_time_only: boolean
  restricted_plan_codes: string[]
  active: boolean
  created_at: string
}

export type AdminPromotionCodeList = {
  enabled: boolean
  stripe_configured: boolean
  synced_with_stripe: boolean
  sync_error: string | null
  codes: AdminPromotionCode[]
}

export type CreatePromotionCodeInput = {
  code: string
  percent_off: number | null
  amount_off_cents: number | null
  duration: "once" | "repeating" | "forever"
  duration_in_months: number | null
  max_redemptions: number | null
  expires_at: string | null
  first_time_only: boolean
  plan_codes: string[]
}

async function adminRequest<T>(path: string, body?: object): Promise<T> {
  const response = await apiFetch(`/api/billing/admin/${path}`, body
    ? { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }
    : { method: "GET" })
  if (!response.ok) throw new Error((await readDetail(response)) ?? "Request failed")
  return (await response.json()) as T
}

export const promotionAdminApi = {
  list: () => adminRequest<AdminPromotionCodeList>("promotion-codes"),
  create: (input: CreatePromotionCodeInput) => adminRequest<AdminPromotionCode>("promotion-codes", input),
  deactivate: (id: string) => adminRequest<{ id: string; status: string }>(`promotion-codes/${id}/deactivate`, {}),
  releaseFounderCheckout: (grantId: string, revoke = false) =>
    adminRequest<{ status: string; expired_checkout_sessions: string[] }>(
      `promotional-offers/${grantId}/release`,
      { revoke },
    ),
}
