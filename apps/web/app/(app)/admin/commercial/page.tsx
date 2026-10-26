"use client"

import { confirmDialog } from "@/components/agents/overlays/confirm"
import { useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { ShieldAlert } from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { PromoCodesAdmin } from "@/components/admin/promo-codes-admin"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PAGE_FRAME } from "@/lib/design-system"
import { apiFetch, fetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { suggestedPromotionCap } from "@/lib/promotions"
import { promotionAdminApi } from "@/lib/promotions-api"

type Category = "unreviewed" | "external" | "internal" | "test"
type Offer = {
  id: string
  offer_type: "trial" | "discount"
  trial_days: number | null
  percent_off: number | null
  discount_months: number | null
  status: string
  valid_until: string | null
  redeemed_at: string | null
  checkout_attempt_id: string | null
  max_promotion_value_cents?: number
}
type Account = {
  org_id: string
  name: string
  customer_category: Category
  classification_reason: string | null
  offers: Offer[]
}
const labels: Record<Category, string> = {
  unreviewed: "Unreviewed",
  external: "External customer",
  internal: "Founder / internal",
  test: "Test / QA",
}
type StripeAccount = {
  customer_id: string | null
  subscriptions: { id: string; status: string; trial_end: number | null; cancel_at_period_end: boolean }[]
  verified_at: string | null
  has_more?: boolean
}
type BillingAlert = { id: string; kind: string; org_id: string | null; occurrences: number }
type Reconciliation = { status: string; summary?: { checked?: number; mismatches?: number; errors?: number } }
async function requestJson(url: string, body?: object): Promise<{ accounts?: Account[]; offers_enabled?: boolean; next_offset?: number; alerts?: BillingAlert[]; reconciliation?: Reconciliation[]; status?: string; mismatches?: number; errors?: number } & Partial<StripeAccount>> {
  const response = await apiFetch(url, body
    ? { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }
    : { method: "GET" })
  const result = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(
    typeof result.detail === "string" ? result.detail : result.detail?.message || "Request failed"
  )
  return result
}

/** Client-side gate; every endpoint is also require_platform_admin on the server. */
export default function CommercialAccountsPage() {
  const { user } = useAuth()
  const { data: me, error: meError } = useSWR<{ platformAdmin?: boolean }>(user ? "/api/auth/me" : null, fetcher)
  const [tab, setTab] = useState<"accounts" | "codes">("accounts")
  if (!user || (!me && !meError)) {
    return (
      <AppShell title="Commercial accounts">
        <p className="p-8 text-sm text-muted-foreground">Checking access…</p>
      </AppShell>
    )
  }
  if (!me?.platformAdmin) {
    return (
      <AppShell title="Commercial accounts">
        <div className="mx-auto max-w-lg space-y-4 p-8 text-center">
          <ShieldAlert className="mx-auto h-10 w-10 text-muted-foreground" aria-hidden />
          <h1 className="text-lg font-semibold">Platform admin access required</h1>
          <p className="text-sm text-muted-foreground">
            Commercial accounts, founder offers and promo codes are managed by Gravitre platform operators. If you
            have a promo code, enter it when you upgrade in Billing.
          </p>
          <Button variant="outline" asChild>
            <Link href="/settings/billing">Go to Billing</Link>
          </Button>
        </div>
      </AppShell>
    )
  }
  return (
    <AppShell title="Commercial accounts">
      <div className={`${PAGE_FRAME} space-y-6 pb-12`}>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Commercial accounts</h1>
            <p className="mt-1 text-sm text-muted-foreground">Founder-only customer classification, Stripe-backed founder offers and public promo codes. Stripe remains the authority for invoices, subscription status and charges.</p>
          </div>
          <div role="tablist" aria-label="Commercial sections" className="flex gap-2">
            <Button role="tab" aria-selected={tab === "accounts"} variant={tab === "accounts" ? "default" : "outline"} size="sm" onClick={() => setTab("accounts")}>Accounts &amp; founder offers</Button>
            <Button role="tab" aria-selected={tab === "codes"} variant={tab === "codes" ? "default" : "outline"} size="sm" onClick={() => setTab("codes")}>Promo codes</Button>
          </div>
        </div>
        {tab === "accounts" ? <CommercialAccountsPanel /> : <PromoCodesAdmin />}
      </div>
    </AppShell>
  )
}

function CommercialAccountsPanel() {
  const { user } = useAuth()
  const [alerts, setAlerts] = useState<BillingAlert[]>([])
  const [reconciliation, setReconciliation] = useState<Reconciliation | null>(null)
  const [promotionCap, setPromotionCap] = useState("")
  const [capEdited, setCapEdited] = useState(false)
  const [classifyExternal, setClassifyExternal] = useState(true)
  const [offersEnabled, setOffersEnabled] = useState(false)
  const [stripeAccount, setStripeAccount] = useState<StripeAccount | null>(null)
  const [stripeError, setStripeError] = useState("")
  const [accounts, setAccounts] = useState<Account[]>([])
  const [selected, setSelected] = useState("")
  const [search, setSearch] = useState("")
  const [category, setCategory] = useState<Category>("unreviewed")
  const [reason, setReason] = useState("")
  const [offerType, setOfferType] = useState<"trial" | "discount">("trial")
  const [trialDays, setTrialDays] = useState(30)
  const [percentOff, setPercentOff] = useState(30)
  const [months, setMonths] = useState(3)
  const [validUntil, setValidUntil] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")

  const refresh = useCallback(async () => {
    if (!user) return
    setLoading(true)
    try {
      const allAccounts: Account[] = []
      let offset = 0
      let enabled = false
      while (true) {
        const data = await requestJson(`/api/billing/admin/commercial-accounts?offset=${offset}&limit=200`)
        allAccounts.push(...(data.accounts || []))
        enabled = data.offers_enabled === true
        if (!data.has_more) break
        if (typeof data.next_offset !== "number" || data.next_offset <= offset) throw new Error("Unable to load the complete account list")
        offset = data.next_offset
      }
      setAccounts(allAccounts)
      setOffersEnabled(enabled)
      const safety = await requestJson("/api/billing/admin/billing-safety")
      setAlerts(safety.alerts || [])
      setReconciliation(safety.reconciliation?.[0] || null)
      setError("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load accounts")
    } finally { setLoading(false) }
  }, [user])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    if (!selected) return
    let canceled = false
    setStripeAccount(null)
    setStripeError("")
    void requestJson(`/api/billing/admin/commercial-accounts/${selected}/stripe`).then(data => {
      if (!canceled) setStripeAccount({
        customer_id: data.customer_id || null, subscriptions: data.subscriptions || [],
        verified_at: data.verified_at || null, has_more: data.has_more,
      })
    }).catch(err => { if (!canceled) setStripeError(err instanceof Error ? err.message : "Stripe verification failed") })
    return () => { canceled = true }
  }, [selected])
  const current = accounts.find(a => a.org_id === selected)
  // Default cap = the largest base-plan value this offer can reach (any plan,
  // monthly or annual), so checkout is never blocked; editable to tighten.
  const capSuggestion = useMemo(() => suggestedPromotionCap(
    offerType === "trial" ? { offerType, trialDays } : { offerType, percentOff, months },
  ), [offerType, trialDays, percentOff, months])
  useEffect(() => {
    if (!capEdited && capSuggestion) setPromotionCap((capSuggestion.cents / 100).toFixed(2))
  }, [capSuggestion, capEdited])
  const needsClassification = current?.customer_category === "unreviewed"
  const canIssue = current?.customer_category === "external" ||
    (needsClassification && classifyExternal && reason.trim().length >= 5)
  const filtered = useMemo(() => accounts.filter(a =>
    `${a.name} ${a.org_id} ${a.customer_category}`.toLowerCase().includes(search.toLowerCase())
  ), [accounts, search])
  const counts = useMemo(() => ({
    external: accounts.filter(a => a.customer_category === "external" && !a.offers.some(o => ["available","redeemed"].includes(o.status))).length,
    promotional: accounts.filter(a => a.customer_category === "external" && a.offers.some(o => ["available","redeemed"].includes(o.status))).length,
    internal: accounts.filter(a => a.customer_category === "internal").length,
    test: accounts.filter(a => a.customer_category === "test").length,
    unreviewed: accounts.filter(a => a.customer_category === "unreviewed").length,
  }), [accounts])

  function choose(account: Account) {
    setSelected(account.org_id)
    setCategory(account.customer_category)
    setReason(account.classification_reason || "")
    setNotice("")
    setError("")
  }
  async function saveCategory() {
    if (!current || reason.trim().length < 5) return
    setSaving(true); setError(""); setNotice("")
    try {
      await requestJson("/api/billing/admin/customer-segments", {
        org_id: current.org_id, customer_category: category, reason: reason.trim(),
      })
      setNotice("Classification saved and audited.")
      await refresh()
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to save") }
    finally { setSaving(false) }
  }
  async function createOffer() {
    if (!current || !canIssue) return
    const capCents = Math.round(Number(promotionCap) * 100)
    if (!Number.isFinite(capCents) || capCents < 1) return
    const terms = offerType === "trial" ? `${trialDays}-day trial` : `${percentOff}% off for ${months} month(s)`
    const classifyNote = needsClassification ? ` ${current.name} will be classified as an External customer ("${reason.trim()}").` : ""
    if (!(await confirmDialog({ title: `Issue ${terms} to ${current.name}?`, description: `Maximum promotional value: $${promotionCap} USD. Stripe applies it at the next eligible checkout.${classifyNote}`, confirmLabel: "Issue offer", tone: "default" }))) return
    setSaving(true); setError(""); setNotice("")
    try {
      await requestJson("/api/billing/admin/promotional-offers", {
        org_id: current.org_id, offer_type: offerType,
        trial_days: offerType === "trial" ? trialDays : null,
        percent_off: offerType === "discount" ? percentOff : null,
        discount_months: offerType === "discount" ? months : null,
        max_promotion_value_cents: capCents,
        valid_until: validUntil ? new Date(`${validUntil}T23:59:59Z`).toISOString() : null,
        ...(needsClassification ? { classify_as_external: true, classification_reason: reason.trim() } : {}),
      })
      setNotice("Founder offer issued. Stripe applies it when the customer checks out.")
      await refresh()
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to create offer") }
    finally { setSaving(false) }
  }
  async function releaseOffer(id: string, revoke: boolean) {
    const question = revoke
      ? "Release the reserved checkout and revoke this offer? Open Stripe Checkout sessions for it are expired first; a completed checkout blocks this."
      : "Release the reserved checkout? Open Stripe Checkout sessions for it are expired so the customer can start a fresh checkout."
    if (!(await confirmDialog({ title: revoke ? "Release and revoke this offer?" : "Release the reserved checkout?", description: question, confirmLabel: revoke ? "Release and revoke" : "Release", tone: revoke ? "danger" : "default" }))) return
    setSaving(true); setError(""); setNotice("")
    try {
      const result = await promotionAdminApi.releaseFounderCheckout(id, revoke)
      setNotice(`Reservation released${result.expired_checkout_sessions.length ? ` (${result.expired_checkout_sessions.length} Stripe session expired)` : ""}${revoke ? " and offer revoked" : ""}.`)
      await refresh()
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to release") }
    finally { setSaving(false) }
  }
  async function revokeOffer(id: string) {
    if (!(await confirmDialog({ title: "Revoke this unredeemed offer?", description: "Its Stripe coupon is deleted; existing Stripe subscriptions are not changed.", confirmLabel: "Revoke offer" }))) return
    setSaving(true); setError(""); setNotice("")
    try {
      await requestJson(`/api/billing/admin/promotional-offers/${id}/revoke`, {})
      setNotice("Offer revoked.")
      await refresh()
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to revoke") }
    finally { setSaving(false) }
  }

  return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          {([
            ["External", counts.external], ["Promotional", counts.promotional],
            ["Internal", counts.internal], ["Test / QA", counts.test],
            ["Unreviewed", counts.unreviewed],
          ] as const).map(([label, count]) =>
            <div key={label} className="rounded-xl border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">{count}</p>
            </div>
          )}
        </div>
        <section className="space-y-2 border-y border-border py-4 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-medium">Billing reconciliation and alerts</h2>
            <Button variant="outline" size="sm" disabled={saving} onClick={() => {
              setSaving(true)
              void requestJson("/api/billing/admin/billing-reconciliation", {}).then(result => {
                setNotice(`Reconciliation ${result.status}: ${result.mismatches || 0} discrepancies, ${result.errors || 0} errors.`)
                return refresh()
              }).catch(err => setError(err instanceof Error ? err.message : "Reconciliation failed")).finally(() => setSaving(false))
            }}>Run reconciliation</Button>
          </div>
          <p className="text-muted-foreground">Latest run: {reconciliation?.status || "Not run"}{reconciliation?.summary ? ` · ${reconciliation.summary.checked || 0} checked · ${reconciliation.summary.mismatches || 0} discrepancies · ${reconciliation.summary.errors || 0} errors` : ""}</p>
          {alerts.length ? <ul role="alert" className="space-y-1">{alerts.map(alert => <li key={alert.id}>{alert.kind.replaceAll("_", " ")} · {alert.org_id || "Platform"} · {alert.occurrences} occurrence(s)</li>)}</ul> : <p className="text-muted-foreground">No unresolved billing alerts.</p>}
          {alerts.length === 100 && <p className="text-muted-foreground">Showing the latest 100 unresolved alerts.</p>}
        </section>
        {error && <p role="alert" className="rounded-lg border border-destructive p-3 text-sm text-destructive">{error}</p>}
        {notice && <p role="status" className="rounded-lg border border-border p-3 text-sm">{notice}</p>}
        <div className="grid gap-5 lg:grid-cols-[minmax(260px,1fr)_minmax(340px,1.3fr)]">
          <section className="rounded-xl border border-border bg-card p-4">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h2 className="font-medium">Organizations</h2>
              <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={loading}>Refresh</Button>
            </div>
            <Input aria-label="Search organizations" placeholder="Search organizations" value={search} onChange={e => setSearch(e.target.value)} />
            <div className="mt-3 max-h-[580px] space-y-1 overflow-y-auto">
              {loading && <p className="p-3 text-sm text-muted-foreground">Loading…</p>}
              {!loading && filtered.map(a =>
                <button key={a.org_id} type="button" onClick={() => choose(a)}
                  className={`w-full rounded-lg border p-3 text-left text-sm transition-colors hover:bg-muted ${selected === a.org_id ? "border-primary bg-muted" : "border-transparent"}`}>
                  <span className="block font-medium">{a.name || "Unnamed organization"}</span>
                  <span className="block text-xs text-muted-foreground">{labels[a.customer_category]}{a.customer_category === "external" && a.offers.some(o => ["available","redeemed"].includes(o.status)) ? " · Promotional" : ""}</span>
                </button>
              )}
              {!loading && !filtered.length && <p className="p-3 text-sm text-muted-foreground">No matching organizations.</p>}
            </div>
          </section>
          <div className="space-y-5">
            {!current && <section className="rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground">Select an organization to review its classification and offers.</section>}
            {current && <>
              <section className="space-y-4 rounded-xl border border-border bg-card p-5">
                <div><h2 className="font-semibold">{current.name}</h2><p className="break-all text-xs text-muted-foreground">{current.org_id}</p></div>
                <div className="space-y-1 border-b border-border pb-4 text-sm">
                  <h3 className="font-medium">Stripe subscription status</h3>
                  {stripeError ? <p role="alert" className="text-destructive">{stripeError}</p> : !stripeAccount ? <p className="text-muted-foreground">Verifying with Stripe…</p> : <>
                    <p className="break-all text-xs text-muted-foreground">{stripeAccount.customer_id || "No Stripe customer linked"}</p>
                    {stripeAccount.customer_id && !stripeAccount.subscriptions.length && <p>No subscriptions in Stripe.</p>}
                    {stripeAccount.subscriptions.map(subscription => <p key={subscription.id}>
                      <span className="font-medium">{subscription.status}</span>
                      <span className="ml-2 text-xs text-muted-foreground">{subscription.id}</span>
                      {subscription.trial_end && subscription.status === "trialing" && <span className="block text-xs">Trial ends {new Date(subscription.trial_end * 1000).toLocaleDateString()}</span>}
                    </p>)}
                    {stripeAccount.has_more && <p>More history is available in Stripe.</p>}
                    <p className="text-xs text-muted-foreground">Trialing subscriptions do not count as paid recurring revenue.</p>
                  </>}
                </div>
                <div>
                  <label htmlFor="category" className="mb-1 block text-sm font-medium">Customer classification</label>
                  <select id="category" value={category} onChange={e => setCategory(e.target.value as Category)} className="w-full rounded-md border border-input bg-background p-2 text-sm">
                    {(Object.keys(labels) as Category[]).map(c => <option key={c} value={c}>{labels[c]}</option>)}
                  </select>
                </div>
                <div>
                  <label htmlFor="reason" className="mb-1 block text-sm font-medium">Classification reason (audited)</label>
                  <Input id="reason" value={reason} onChange={e => setReason(e.target.value)} placeholder="Evidence for this classification" maxLength={500} />
                </div>
                <Button onClick={() => void saveCategory()} disabled={saving || reason.trim().length < 5}>Save classification</Button>
              </section>
              <section className="space-y-4 rounded-xl border border-border bg-card p-5">
                <div><h2 className="font-semibold">Founder promotional offer</h2><p className="text-xs text-muted-foreground">Promotions are an acquisition segment, not a separate billing plan. Only external customers can receive offers.</p></div>
                <div className="flex gap-2">
                  <Button variant={offerType === "trial" ? "default" : "outline"} onClick={() => setOfferType("trial")}>Free trial</Button>
                  <Button variant={offerType === "discount" ? "default" : "outline"} onClick={() => setOfferType("discount")}>Percentage off</Button>
                </div>
                {offerType === "trial" ?
                  <div><label htmlFor="trial-days" className="mb-1 block text-sm">Trial length (days)</label><Input id="trial-days" type="number" min={1} max={90} value={trialDays} onChange={e => setTrialDays(Number(e.target.value))}/></div> :
                  <div className="grid grid-cols-2 gap-3">
                    <div><label htmlFor="percent-off" className="mb-1 block text-sm">Discount (%)</label><Input id="percent-off" type="number" min={1} max={100} value={percentOff} onChange={e => setPercentOff(Number(e.target.value))}/></div>
                    <div><label htmlFor="discount-months" className="mb-1 block text-sm">Duration (months)</label><Input id="discount-months" type="number" min={1} max={12} value={months} onChange={e => setMonths(Number(e.target.value))}/></div>
                  </div>
                }
                <div><label htmlFor="offer-expiry" className="mb-1 block text-sm">Offer redemption deadline (optional)</label><Input id="offer-expiry" type="date" value={validUntil} onChange={e => setValidUntil(e.target.value)}/></div>
                <div>
                  <label htmlFor="promotion-cap" className="mb-1 block text-sm">Maximum promotional value (USD)</label>
                  <Input id="promotion-cap" type="number" min="0.01" step="0.01" value={promotionCap} onChange={e => { setCapEdited(true); setPromotionCap(e.target.value) }} />
                  <p className="mt-1 text-xs text-muted-foreground">
                    {capSuggestion ? <>Suggested ${(capSuggestion.cents / 100).toFixed(2)}: {capSuggestion.explanation} </> : null}
                    Checkout is blocked if the base-plan trial or discount value exceeds this cap, so a lower cap limits which plan the customer can choose. Trials reserve included usage before execution and cannot auto-top-up.
                    {capEdited && capSuggestion ? <> <button type="button" className="underline" onClick={() => setCapEdited(false)}>Use suggested</button></> : null}
                  </p>
                </div>
                {needsClassification && (
                  <div className="space-y-2 rounded-lg border border-border p-3 text-sm">
                    <label className="flex items-center gap-2">
                      <input type="checkbox" checked={classifyExternal} onChange={e => setClassifyExternal(e.target.checked)} />
                      Classify as External customer in the same step
                    </label>
                    <p className="text-xs text-muted-foreground">Uses the classification reason above (at least 5 characters). The change is audited.</p>
                  </div>
                )}
                <Button onClick={() => void createOffer()} disabled={!Number.isFinite(Number(promotionCap)) || Number(promotionCap) <= 0 || !offersEnabled || saving || !canIssue || current.offers.some(o => o.status === "available") || (offerType === "trial" ? trialDays < 1 || trialDays > 90 : percentOff <= 0 || percentOff > 100 || months < 1 || months > 12)}>Issue offer</Button>
                {!offersEnabled && <p className="text-xs text-muted-foreground">Offer issuance is disabled until checkout and trial lifecycle verification is complete.</p>}
                {current.customer_category !== "external" && !needsClassification && <p className="text-xs text-muted-foreground">Only external customers can receive offers. Internal and test organizations are excluded.</p>}
                {needsClassification && !canIssue && <p className="text-xs text-muted-foreground">Add a classification reason above and keep &quot;Classify as External&quot; checked to issue an offer.</p>}
                <div className="space-y-2 border-t border-border pt-3">
                  <h3 className="text-sm font-medium">Offer history</h3>
                  {!current.offers.length && <p className="text-xs text-muted-foreground">No offers issued.</p>}
                  {current.offers.map(o => <div key={o.id} className="flex items-center justify-between gap-2 rounded-lg border border-border p-3 text-sm">
                    <span>{o.offer_type === "trial" ? `${o.trial_days} day trial` : `${o.percent_off}% off for ${o.discount_months} month(s)`} <span className="text-xs text-muted-foreground">· {o.checkout_attempt_id && o.status === "available" ? "Checkout reserved" : o.status}</span></span>
                    {o.status === "available" && !o.checkout_attempt_id && <Button size="sm" variant="outline" disabled={saving} onClick={() => void revokeOffer(o.id)}>Revoke</Button>}
                    {o.status === "available" && o.checkout_attempt_id && <span className="flex shrink-0 gap-1">
                      <Button size="sm" variant="outline" disabled={saving} onClick={() => void releaseOffer(o.id, false)}>Release</Button>
                      <Button size="sm" variant="outline" disabled={saving} onClick={() => void releaseOffer(o.id, true)}>Release &amp; revoke</Button>
                    </span>}
                  </div>)}
                </div>
                {current.offers.some(o => o.status === "available" && o.checkout_attempt_id) && <p className="text-xs text-muted-foreground">A checkout is reserved. Release verifies Stripe first: open sessions are expired, and a completed checkout or live subscription blocks the release. Ambiguous attempts are never retried as a new subscription.</p>}
              </section>
            </>}
          </div>
        </div>
      </div>
  )
}
