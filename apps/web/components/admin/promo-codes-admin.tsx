"use client"

import { confirmDialog } from "@/components/agents/overlays/confirm"
import { useCallback, useEffect, useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { describePromoTerms } from "@/lib/promotions"
import {
  promotionAdminApi,
  type AdminPromotionCode,
  type AdminPromotionCodeList,
} from "@/lib/promotions-api"

const PLANS = [
  { code: "node", label: "Node" },
  { code: "control", label: "Control" },
  { code: "command", label: "Command" },
] as const

const STATUS_LABEL: Record<AdminPromotionCode["status"], string> = {
  active: "Active",
  inactive: "Deactivated",
  expired: "Expired",
  exhausted: "Limit reached",
}

/**
 * Platform-admin catalog of public promo codes. Each code is a Stripe Coupon
 * (restricted to base-plan products) plus a Stripe PromotionCode; Stripe
 * enforces limits, expiry and first-time rules at checkout.
 */
export function PromoCodesAdmin() {
  const [list, setList] = useState<AdminPromotionCodeList | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [code, setCode] = useState("")
  const [kind, setKind] = useState<"percent" | "amount">("percent")
  const [percentOff, setPercentOff] = useState(30)
  const [amountOff, setAmountOff] = useState(20)
  const [duration, setDuration] = useState<"once" | "repeating" | "forever">("repeating")
  const [months, setMonths] = useState(3)
  const [maxRedemptions, setMaxRedemptions] = useState("")
  const [expiresOn, setExpiresOn] = useState("")
  const [firstTimeOnly, setFirstTimeOnly] = useState(false)
  const [plans, setPlans] = useState<string[]>([])

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      setList(await promotionAdminApi.list())
      setError("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load promo codes")
    } finally {
      setLoading(false)
    }
  }, [])
  useEffect(() => {
    void refresh()
  }, [refresh])

  const normalizedCode = code.trim().toUpperCase()
  const codeValid = /^[A-Z0-9][A-Z0-9_-]{2,39}$/.test(normalizedCode)
  const valueValid = kind === "percent" ? percentOff > 0 && percentOff <= 100 : amountOff >= 1
  const monthsValid = duration !== "repeating" || (months >= 1 && months <= 36)
  const preview = useMemo(
    () =>
      describePromoTerms({
        percent_off: kind === "percent" ? percentOff : null,
        amount_off_cents: kind === "amount" ? Math.round(amountOff * 100) : null,
        duration,
        duration_in_months: duration === "repeating" ? months : null,
      }),
    [kind, percentOff, amountOff, duration, months],
  )

  async function create() {
    if (!codeValid || !valueValid || !monthsValid) return
    const limit = maxRedemptions ? Number(maxRedemptions) : null
    if (limit !== null && (!Number.isInteger(limit) || limit < 1)) {
      setError("Max redemptions must be a whole number")
      return
    }
    const planText = plans.length && plans.length < 3 ? ` on ${plans.join(", ")}` : " on every plan"
    if (!(await confirmDialog({ title: `Create public code ${normalizedCode}?`, description: `${preview}${planText}. Anyone with the code can use it at checkout.`, confirmLabel: "Create code", tone: "default" }))) return
    setSaving(true)
    setError("")
    setNotice("")
    try {
      const created = await promotionAdminApi.create({
        code: normalizedCode,
        percent_off: kind === "percent" ? percentOff : null,
        amount_off_cents: kind === "amount" ? Math.round(amountOff * 100) : null,
        duration,
        duration_in_months: duration === "repeating" ? months : null,
        max_redemptions: limit,
        expires_at: expiresOn ? new Date(`${expiresOn}T23:59:59Z`).toISOString() : null,
        first_time_only: firstTimeOnly,
        plan_codes: plans,
      })
      setNotice(`Created ${created.code}: ${created.summary}. Share links as /pricing?promo=${created.code}.`)
      setCode("")
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create promo code")
    } finally {
      setSaving(false)
    }
  }

  async function deactivate(row: AdminPromotionCode) {
    if (!(await confirmDialog({ title: `Deactivate ${row.code}?`, description: "New checkouts can no longer use it; existing discounts continue.", confirmLabel: "Deactivate" }))) return
    setSaving(true)
    setError("")
    setNotice("")
    try {
      await promotionAdminApi.deactivate(row.id)
      setNotice(`${row.code} deactivated in Stripe.`)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to deactivate")
    } finally {
      setSaving(false)
    }
  }

  const disabled = list ? !list.enabled || !list.stripe_configured : false

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(320px,1fr)_minmax(360px,1.4fr)]">
      <section className="space-y-4 rounded-xl border border-border bg-card p-5" aria-labelledby="promo-create-title">
        <div>
          <h2 id="promo-create-title" className="font-semibold">Create a public promo code</h2>
          <p className="text-xs text-muted-foreground">
            Usable by anyone at checkout (pricing, signup and in-app upgrade). Discounts apply to base plans only, never
            usage overages, and are never combined with a founder offer.
          </p>
        </div>
        {list && !list.enabled && <p className="text-xs text-destructive">Promo codes are disabled (PROMOTION_CODES_ENABLED=false).</p>}
        {list && !list.stripe_configured && <p className="text-xs text-destructive">Stripe is not configured; codes cannot be created.</p>}
        <div>
          <label htmlFor="promo-code" className="mb-1 block text-sm">Code</label>
          <Input id="promo-code" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="LAUNCH30" maxLength={40} className="font-mono" />
          {code && !codeValid && <p className="mt-1 text-xs text-destructive">3–40 letters, numbers, dashes or underscores.</p>}
        </div>
        <div className="flex gap-2">
          <Button type="button" variant={kind === "percent" ? "default" : "outline"} onClick={() => setKind("percent")}>% off</Button>
          <Button type="button" variant={kind === "amount" ? "default" : "outline"} onClick={() => setKind("amount")}>$ off</Button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {kind === "percent" ? (
            <div><label htmlFor="promo-percent" className="mb-1 block text-sm">Discount (%)</label><Input id="promo-percent" type="number" min={1} max={100} value={percentOff} onChange={(e) => setPercentOff(Number(e.target.value))} /></div>
          ) : (
            <div><label htmlFor="promo-amount" className="mb-1 block text-sm">Amount off (USD)</label><Input id="promo-amount" type="number" min={1} step="0.01" value={amountOff} onChange={(e) => setAmountOff(Number(e.target.value))} /></div>
          )}
          <div>
            <label htmlFor="promo-duration" className="mb-1 block text-sm">Duration</label>
            <select id="promo-duration" value={duration} onChange={(e) => setDuration(e.target.value as typeof duration)} className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm">
              <option value="once">First payment only</option>
              <option value="repeating">Several months</option>
              <option value="forever">Forever</option>
            </select>
          </div>
          {duration === "repeating" && (
            <div><label htmlFor="promo-months" className="mb-1 block text-sm">Months</label><Input id="promo-months" type="number" min={1} max={36} value={months} onChange={(e) => setMonths(Number(e.target.value))} /></div>
          )}
          <div><label htmlFor="promo-max" className="mb-1 block text-sm">Max redemptions</label><Input id="promo-max" type="number" min={1} value={maxRedemptions} onChange={(e) => setMaxRedemptions(e.target.value)} placeholder="Unlimited" /></div>
          <div><label htmlFor="promo-expiry" className="mb-1 block text-sm">Expires (optional)</label><Input id="promo-expiry" type="date" value={expiresOn} onChange={(e) => setExpiresOn(e.target.value)} /></div>
        </div>
        <fieldset className="space-y-2">
          <legend className="text-sm">Plans</legend>
          <div className="flex flex-wrap gap-3 text-sm">
            {PLANS.map((plan) => (
              <label key={plan.code} className="inline-flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={plans.includes(plan.code)}
                  onChange={(e) => setPlans((current) => (e.target.checked ? [...current, plan.code] : current.filter((p) => p !== plan.code)))}
                />
                {plan.label}
              </label>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">None selected means every paid plan.</p>
        </fieldset>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={firstTimeOnly} onChange={(e) => setFirstTimeOnly(e.target.checked)} />
          New customers only (Stripe first-time transaction)
        </label>
        <p className="text-xs text-muted-foreground">Preview: <span className="font-medium text-foreground">{preview}</span></p>
        <Button onClick={() => void create()} disabled={saving || disabled || !codeValid || !valueValid || !monthsValid}>Create code</Button>
      </section>

      <section className="space-y-3 rounded-xl border border-border bg-card p-5" aria-labelledby="promo-list-title">
        <div className="flex items-center justify-between gap-2">
          <h2 id="promo-list-title" className="font-semibold">Promo codes</h2>
          <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={loading}>Refresh from Stripe</Button>
        </div>
        {error && <p role="alert" className="rounded-lg border border-destructive p-3 text-sm text-destructive">{error}</p>}
        {notice && <p role="status" className="rounded-lg border border-border p-3 text-sm">{notice}</p>}
        {list?.sync_error && <p className="text-xs text-destructive">Stripe refresh failed: {list.sync_error}. Showing cached counts.</p>}
        {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {!loading && !list?.codes.length && <p className="text-sm text-muted-foreground">No promo codes yet.</p>}
        <ul className="space-y-2">
          {list?.codes.map((row) => (
            <li key={row.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border p-3 text-sm">
              <div className="min-w-0">
                <p><span className="font-mono font-semibold">{row.code}</span> <span className="text-muted-foreground">· {row.summary}</span></p>
                <p className="text-xs text-muted-foreground">
                  {STATUS_LABEL[row.status]} · {row.times_redeemed}{row.max_redemptions ? ` / ${row.max_redemptions}` : ""} redeemed
                  {row.expires_at ? ` · expires ${new Date(row.expires_at).toLocaleDateString()}` : ""}
                </p>
              </div>
              {row.active && (
                <Button size="sm" variant="outline" disabled={saving} onClick={() => void deactivate(row)}>Deactivate</Button>
              )}
            </li>
          ))}
        </ul>
        {list && <p className="text-xs text-muted-foreground">{list.synced_with_stripe ? "Redemption counts verified with Stripe just now." : "Counts are cached from the last Stripe refresh and verified webhooks."}</p>}
      </section>
    </div>
  )
}
