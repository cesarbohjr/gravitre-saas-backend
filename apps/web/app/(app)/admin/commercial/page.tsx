"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PAGE_FRAME } from "@/lib/design-system"
import { apiFetch } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"

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
async function requestJson(url: string, body?: object): Promise<{ accounts?: Account[]; detail?: string | { message?: string } }> {
  const response = await apiFetch(url, body
    ? { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }
    : { method: "GET" })
  const result = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(
    typeof result.detail === "string" ? result.detail : result.detail?.message || "Request failed"
  )
  return result
}

export default function CommercialAccountsPage() {
  const { user } = useAuth()
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
      const data = await requestJson("/api/billing/admin/commercial-accounts")
      setAccounts(data.accounts || [])
      setError("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load accounts")
    } finally { setLoading(false) }
  }, [user])

  useEffect(() => { void refresh() }, [refresh])
  const current = accounts.find(a => a.org_id === selected)
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
    if (!current || current.customer_category !== "external") return
    const terms = offerType === "trial" ? `${trialDays}-day trial` : `${percentOff}% off for ${months} month(s)`
    if (!window.confirm(`Issue ${terms} to ${current.name}? This will create a Stripe-backed offer for the next eligible checkout.`)) return
    setSaving(true); setError(""); setNotice("")
    try {
      await requestJson("/api/billing/admin/promotional-offers", {
        org_id: current.org_id, offer_type: offerType,
        trial_days: offerType === "trial" ? trialDays : null,
        percent_off: offerType === "discount" ? percentOff : null,
        discount_months: offerType === "discount" ? months : null,
        valid_until: validUntil ? new Date(`${validUntil}T23:59:59Z`).toISOString() : null,
      })
      setNotice("Founder offer issued. Stripe applies it when the customer checks out.")
      await refresh()
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to create offer") }
    finally { setSaving(false) }
  }
  async function revokeOffer(id: string) {
    if (!window.confirm("Revoke this unredeemed offer? Existing Stripe subscriptions are not changed.")) return
    setSaving(true); setError(""); setNotice("")
    try {
      await requestJson(`/api/billing/admin/promotional-offers/${id}/revoke`, {})
      setNotice("Offer revoked.")
      await refresh()
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to revoke") }
    finally { setSaving(false) }
  }

  return (
    <AppShell title="Commercial accounts">
      <div className={`${PAGE_FRAME} space-y-6 pb-12`}>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Commercial accounts</h1>
          <p className="mt-1 text-sm text-muted-foreground">Founder-only customer classification and Stripe-backed promotional offers. Stripe remains the authority for invoices, subscription status and charges.</p>
        </div>
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
                <Button onClick={() => void createOffer()} disabled={saving || current.customer_category !== "external" || current.offers.some(o => o.status === "available") || (offerType === "trial" ? trialDays < 1 || trialDays > 90 : percentOff <= 0 || percentOff > 100 || months < 1 || months > 12)}>Issue offer</Button>
                {current.customer_category !== "external" && <p className="text-xs text-muted-foreground">Classify this organization as an external customer before issuing an offer.</p>}
                <div className="space-y-2 border-t border-border pt-3">
                  <h3 className="text-sm font-medium">Offer history</h3>
                  {!current.offers.length && <p className="text-xs text-muted-foreground">No offers issued.</p>}
                  {current.offers.map(o => <div key={o.id} className="flex items-center justify-between gap-2 rounded-lg border border-border p-3 text-sm">
                    <span>{o.offer_type === "trial" ? `${o.trial_days} day trial` : `${o.percent_off}% off for ${o.discount_months} month(s)`} <span className="text-xs text-muted-foreground">· {o.status}</span></span>
                    {o.status === "available" && <Button size="sm" variant="outline" disabled={saving} onClick={() => void revokeOffer(o.id)}>Revoke</Button>}
                  </div>)}
                </div>
              </section>
            </>}
          </div>
        </div>
      </div>
    </AppShell>
  )
}
