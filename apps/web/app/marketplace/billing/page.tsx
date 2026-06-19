"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { marketplaceApi } from "@/lib/api"
import { fetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { ArrowLeft, CreditCard, DollarSign, Loader2, RefreshCw } from "lucide-react"
import { toast } from "sonner"
import type {
  MarketplaceAssetPayoutRow,
  MarketplaceBillingStatus,
  MarketplacePartnerPricing,
} from "@/types/api"

function formatUsd(cents: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(cents / 100)
}

const PRICING_LABELS: Record<string, string> = {
  free: "Free",
  flat_monthly: "Flat monthly",
  per_invocation: "Per invocation",
}

function PricingRow({
  item,
  platformFeeBps,
  onSaved,
}: {
  item: MarketplacePartnerPricing
  platformFeeBps: number
  onSaved: () => void
}) {
  const [model, setModel] = useState(item.pricingModel)
  const [priceDollars, setPriceDollars] = useState(String((item.priceCents || 0) / 100))
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      const priceCents = model === "free" ? 0 : Math.round(parseFloat(priceDollars || "0") * 100)
      await marketplaceApi.upsertPricing(item.registryId, {
        pricingModel: model,
        priceCents,
        currency: "usd",
      })
      toast.success("Pricing updated", { description: item.connectorName ?? item.vendor ?? "Connector" })
      onSaved()
    } catch (err) {
      toast.error("Could not save pricing", {
        description: err instanceof Error ? err.message : "Try again",
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="rounded-md border border-border p-4 space-y-3">
      <div>
        <p className="text-sm font-medium">{item.connectorName ?? item.vendor}</p>
        <p className="text-xs text-muted-foreground">Platform fee: {platformFeeBps / 100}%</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {(["free", "flat_monthly", "per_invocation"] as const).map((option) => (
          <Button
            key={option}
            type="button"
            size="sm"
            variant={model === option ? "default" : "outline"}
            onClick={() => setModel(option)}
          >
            {PRICING_LABELS[option]}
          </Button>
        ))}
      </div>
      {model !== "free" && (
        <div className="flex items-center gap-2 max-w-xs">
          <span className="text-sm text-muted-foreground">$</span>
          <Input
            type="number"
            min="0"
            step="0.01"
            value={priceDollars}
            onChange={(e) => setPriceDollars(e.target.value)}
          />
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            {model === "per_invocation" ? "/ invoke" : "/ month"}
          </span>
        </div>
      )}
      <Button size="sm" onClick={() => void handleSave()} disabled={saving}>
        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save pricing"}
      </Button>
    </div>
  )
}

export default function MarketplaceBillingPage() {
  const { user } = useAuth()
  const [isWorking, setIsWorking] = useState(false)

  const { data, mutate, isLoading } = useSWR<MarketplaceBillingStatus>(
    user ? "/api/marketplace/billing/status" : null,
    fetcher
  )

  const { data: pricingData, mutate: mutatePricing } = useSWR<{ pricing: MarketplacePartnerPricing[] }>(
    user ? "/api/marketplace/billing/pricing" : null,
    fetcher
  )

  const pricing: MarketplacePartnerPricing[] = pricingData?.pricing ?? []
  const account = data?.account
  const earnings = data?.earnings

  const handleOnboard = async () => {
    setIsWorking(true)
    try {
      const base = window.location.origin
      const result = await marketplaceApi.connectOnboard({
        returnUrl: `${base}/marketplace/billing?connect=return`,
        refreshUrl: `${base}/marketplace/billing?connect=refresh`,
      })
      window.location.assign(result.url)
    } catch (err) {
      toast.error("Stripe Connect onboarding failed", {
        description: err instanceof Error ? err.message : "Try again",
      })
      setIsWorking(false)
    }
  }

  const handleSync = async () => {
    setIsWorking(true)
    try {
      await marketplaceApi.syncConnectAccount()
      toast.success("Connect account synced")
      await mutate()
    } catch (err) {
      toast.error("Sync failed", { description: err instanceof Error ? err.message : "Try again" })
    } finally {
      setIsWorking(false)
    }
  }

  const handlePayoutSync = async () => {
    setIsWorking(true)
    try {
      const result = await marketplaceApi.syncPublisherPayouts()
      const { transferred, failed, pendingReviewed } = result.sync
      if (pendingReviewed === 0) {
        toast.success("No pending asset payouts to sync")
      } else if (transferred > 0) {
        toast.success(`Transferred ${transferred} asset payout${transferred === 1 ? "" : "s"}`)
      } else if (failed > 0) {
        toast.error(`${failed} payout transfer${failed === 1 ? "" : "s"} failed`, {
          description: "Check Stripe Connect status and try again",
        })
      } else {
        toast.message("Pending payouts reviewed", {
          description: "Connect may still be onboarding — transfers retry when active",
        })
      }
      await mutate()
    } catch (err) {
      toast.error("Payout sync failed", { description: err instanceof Error ? err.message : "Try again" })
    } finally {
      setIsWorking(false)
    }
  }

  const assetPayouts = data?.assetPayouts
  const recentAssetPayouts: MarketplaceAssetPayoutRow[] = data?.recentAssetPayouts ?? []

  return (
    <AppShell title="Partner billing">
      <div className="mx-auto max-w-3xl p-6 space-y-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
              <DollarSign className="h-4 w-4" />
              Marketplace · Billing
            </div>
            <h1 className="text-2xl font-semibold">Partner revenue & payouts</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Connect Stripe to receive payouts, set connector pricing, and track usage-based earnings.
            </p>
          </div>
          <Button variant="outline" size="sm" asChild>
            <Link href="/marketplace/submit">
              <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
              Submit
            </Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href="/marketplace/publisher/analytics">Revenue analytics</Link>
          </Button>
        </div>

        {isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading billing status...
          </div>
        ) : (
          <>
            <div className="rounded-lg border border-border bg-card p-5 space-y-4">
              <div className="flex items-center gap-2">
                <CreditCard className="h-4 w-4 text-muted-foreground" />
                <p className="text-sm font-medium">Stripe Connect</p>
              </div>
              <p className="text-sm text-muted-foreground">
                Status:{" "}
                <span className="font-mono text-foreground">{account?.connectStatus ?? "pending"}</span>
                {account?.chargesEnabled && account?.payoutsEnabled ? " · ready for payouts" : ""}
              </p>
              <div className="flex flex-wrap gap-2">
                {account?.connectStatus !== "active" ? (
                  <Button onClick={() => void handleOnboard()} disabled={isWorking} className="gap-2">
                    {isWorking ? <Loader2 className="h-4 w-4 animate-spin" /> : <CreditCard className="h-4 w-4" />}
                    Connect Stripe payouts
                  </Button>
                ) : null}
                <Button variant="outline" onClick={() => void handleSync()} disabled={isWorking} className="gap-2">
                  <RefreshCw className="h-4 w-4" />
                  Sync account
                </Button>
              </div>
            </div>

            {earnings && (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  { label: "Connector gross", value: formatUsd(earnings.grossCents) },
                  { label: "Connector earnings", value: formatUsd(earnings.partnerEarningsCents) },
                  { label: "Connector transferred", value: formatUsd(earnings.transferredCents) },
                  { label: "Active installs", value: String(earnings.activeInstallCount) },
                ].map((stat) => (
                  <div key={stat.label} className="rounded-md border border-border bg-muted/20 p-4">
                    <p className="text-xs text-muted-foreground">{stat.label}</p>
                    <p className="text-lg font-semibold mt-1">{stat.value}</p>
                  </div>
                ))}
              </div>
            )}

            <div className="rounded-lg border border-border bg-card p-5 space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium">Unified asset payouts</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Revenue from paid marketplace asset purchases (one-time and subscription).
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void handlePayoutSync()}
                  disabled={isWorking}
                  className="gap-2"
                >
                  {isWorking ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                  Sync pending payouts
                </Button>
              </div>

              {assetPayouts && assetPayouts.payoutCount > 0 ? (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {[
                    { label: "Asset sales", value: formatUsd(assetPayouts.grossCents) },
                    { label: "Your share", value: formatUsd(assetPayouts.partnerEarningsCents) },
                    { label: "Transferred", value: formatUsd(assetPayouts.transferredCents) },
                    { label: "Pending transfer", value: formatUsd(assetPayouts.pendingTransferCents) },
                  ].map((stat) => (
                    <div key={stat.label} className="rounded-md border border-border bg-muted/20 p-4">
                      <p className="text-xs text-muted-foreground">{stat.label}</p>
                      <p className="text-lg font-semibold mt-1">{stat.value}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No paid asset sales recorded yet.</p>
              )}

              {recentAssetPayouts.length > 0 ? (
                <div className="rounded border border-border overflow-x-auto">
                  <table className="w-full text-xs min-w-[520px]">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium">Asset</th>
                        <th className="text-left px-3 py-2 font-medium">Gross</th>
                        <th className="text-left px-3 py-2 font-medium">Earnings</th>
                        <th className="text-left px-3 py-2 font-medium">Status</th>
                        <th className="text-left px-3 py-2 font-medium">Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentAssetPayouts.map((row) => (
                        <tr key={row.id} className="border-t border-border">
                          <td className="px-3 py-2">
                            {row.assetTitle ?? row.assetSlug ?? row.assetId ?? "Asset"}
                          </td>
                          <td className="px-3 py-2">{formatUsd(row.grossCents)}</td>
                          <td className="px-3 py-2">{formatUsd(row.partnerEarningsCents)}</td>
                          <td className="px-3 py-2 text-muted-foreground">{row.status}</td>
                          <td className="px-3 py-2 text-muted-foreground">
                            {row.createdAt ? new Date(row.createdAt).toLocaleString() : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>

            <div className="space-y-3">
              <h2 className="text-sm font-medium">Connector pricing</h2>
              {pricing.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Publish a connector to the marketplace before setting pricing.
                </p>
              ) : (
                pricing.map((item) => (
                  <PricingRow
                    key={item.registryId}
                    item={item}
                    platformFeeBps={data?.platformFeeBps ?? 2000}
                    onSaved={() => void mutatePricing()}
                  />
                ))
              )}
            </div>

            {data?.recentUsage && data.recentUsage.length > 0 && (
              <div className="space-y-2">
                <h2 className="text-sm font-medium">Recent usage</h2>
                <div className="rounded border border-border overflow-x-auto">
                  <table className="w-full text-xs min-w-[460px]">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium">Action</th>
                        <th className="text-left px-3 py-2 font-medium">Earnings</th>
                        <th className="text-left px-3 py-2 font-medium">Transfer</th>
                        <th className="text-left px-3 py-2 font-medium">Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recentUsage.map((row) => (
                        <tr key={row.id} className="border-t border-border">
                          <td className="px-3 py-2 font-mono">{row.action}</td>
                          <td className="px-3 py-2">{formatUsd(row.partnerEarningsCents)}</td>
                          <td className="px-3 py-2 text-muted-foreground">{row.transferStatus}</td>
                          <td className="px-3 py-2 text-muted-foreground">
                            {row.createdAt ? new Date(row.createdAt).toLocaleString() : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  )
}
