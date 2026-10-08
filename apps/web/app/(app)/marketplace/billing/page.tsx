"use client"

import { useMemo, useRef, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { AppShell } from "@/components/gravitre/app-shell"
import { AdaptiveDataView } from "@/components/gravitre/adaptive-data-view"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { marketplaceApi } from "@/lib/api"
import { fetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { cn } from "@/lib/utils"
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  CreditCard,
  DollarSign,
  Loader2,
  RefreshCw,
  TrendingUp,
} from "lucide-react"
import { toast } from "sonner"
import type {
  MarketplaceAssetPayoutRow,
  MarketplaceAssetPayoutSummary,
  MarketplaceBillingStatus,
  MarketplacePartnerPricing,
  MarketplacePublisherPayoutSyncResult,
} from "@/types/api"
import { Illustration } from "@/components/gravitre/illustration"

function formatUsd(cents: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(cents / 100)
}

const PRICING_LABELS: Record<string, string> = {
  free: "Free",
  flat_monthly: "Flat monthly",
  per_invocation: "Per invocation",
}

function payoutStatusVariant(status: string) {
  if (status === "transferred") return "default"
  if (status === "failed") return "destructive"
  return "secondary"
}

function connectReady(
  account: MarketplaceBillingStatus["account"] | undefined,
) {
  return (
    account?.connectStatus === "active" &&
    Boolean(account?.chargesEnabled && account?.payoutsEnabled)
  )
}

function transferRate(summary: MarketplaceAssetPayoutSummary) {
  const earned = summary.partnerEarningsCents
  if (earned <= 0) return 0
  return Math.min(100, (summary.transferredCents / earned) * 100)
}

function PayoutTransferHero({
  summary,
}: {
  summary: MarketplaceAssetPayoutSummary
}) {
  const rate = transferRate(summary)
  return (
    <div className="rounded-lg border border-border bg-muted/20 p-4">
      <div
        data-composition="configure"
        className="mb-3 flex flex-wrap items-start justify-between gap-2"
      >
        <div>
          <p className="text-sm font-medium">Asset payout transfer rate</p>
          <p className="text-xs text-muted-foreground">
            Share of your asset earnings already transferred to Stripe Connect.
          </p>
        </div>
        <Badge
          variant={
            rate >= 90
              ? "default"
              : summary.pendingTransferCents > 0
                ? "secondary"
                : "outline"
          }
        >
          {rate.toFixed(1)}% transferred
        </Badge>
      </div>
      <Progress value={rate} className="mb-2 h-2.5" />
      <div className="flex flex-wrap justify-between gap-2 text-xs text-muted-foreground">
        <span>{formatUsd(summary.transferredCents)} transferred</span>
        <span>{formatUsd(summary.pendingTransferCents)} pending</span>
      </div>
    </div>
  )
}

function LastSyncResult({
  result,
}: {
  result: MarketplacePublisherPayoutSyncResult
}) {
  return (
    <div className="rounded-lg border border-border bg-muted/10 p-3 text-sm">
      <p className="mb-2 flex items-center gap-2 font-medium">
        <CheckCircle2 className="h-4 w-4 text-success" aria-hidden />
        Last sync result
      </p>
      <dl className="grid gap-2 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-muted-foreground">Reviewed</dt>
          <dd className="font-medium tabular-nums">{result.pendingReviewed}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Transferred</dt>
          <dd className="font-medium tabular-nums text-success">
            {result.transferred}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Failed</dt>
          <dd
            className={cn(
              "font-medium tabular-nums",
              result.failed > 0 && "text-destructive",
            )}
          >
            {result.failed}
          </dd>
        </div>
      </dl>
    </div>
  )
}

function PricingRow({
  item,
  platformFeeBps,
  onSaved,
}: {
  item: MarketplacePartnerPricing
  platformFeeBps?: number
  onSaved: () => void
}) {
  const [model, setModel] = useState(item.pricingModel)
  const [priceDollars, setPriceDollars] = useState(
    String((item.priceCents || 0) / 100),
  )
  const lock = useRef(false)
  const [failure, setFailure] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    if (lock.current) return
    const amount = priceDollars.trim()
    const priceCents = model === "free" ? 0 : Math.round(Number(amount) * 100)
    if (
      model !== "free" &&
      (!/^\d+(\.\d{1,2})?$/.test(amount) ||
        !Number.isSafeInteger(priceCents) ||
        priceCents < 1)
    ) {
      setFailure("Enter a positive USD amount with at most two decimal places.")
      return
    }
    lock.current = true
    setFailure(null)
    setSaving(true)
    try {
      await marketplaceApi.upsertPricing(item.registryId, {
        pricingModel: model,
        priceCents,
        currency: "usd",
      })
      toast.success("Pricing updated", {
        description: item.connectorName ?? item.vendor ?? "Connector",
      })
      onSaved()
    } catch (err) {
      setFailure(
        err instanceof Error
          ? err.message
          : "Pricing could not be saved. Your edits are retained.",
      )
    } finally {
      lock.current = false
      setSaving(false)
    }
  }

  return (
    <div className="space-y-3 rounded-md border border-border p-4">
      <div>
        <p className="text-sm font-medium">
          {item.connectorName ?? item.vendor}
        </p>
        <p className="text-xs text-muted-foreground">
          Platform fee:{" "}
          {platformFeeBps == null ? "Not reported" : `${platformFeeBps / 100}%`}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {(["free", "flat_monthly", "per_invocation"] as const).map((option) => (
          <Button
            key={option}
            type="button"
            size="sm"
            variant={model === option ? "default" : "outline"}
            disabled={saving}
            aria-pressed={model === option}
            onClick={() => setModel(option)}
          >
            {PRICING_LABELS[option]}
          </Button>
        ))}
      </div>
      {model !== "free" ? (
        <div className="flex max-w-xs items-center gap-2">
          <span className="text-sm text-muted-foreground">$</span>
          <Input
            type="number"
            min="0.01"
            aria-label="Connector price in USD"
            disabled={saving}
            step="0.01"
            value={priceDollars}
            onChange={(event) => setPriceDollars(event.target.value)}
          />
          <span className="whitespace-nowrap text-xs text-muted-foreground">
            {model === "per_invocation" ? "/ invoke" : "/ month"}
          </span>
        </div>
      ) : null}
      {failure ? (
        <p role="alert" className="text-sm text-destructive">
          {failure}
        </p>
      ) : null}
      <Button size="sm" onClick={() => void handleSave()} disabled={saving}>
        {saving ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        ) : (
          "Save pricing"
        )}
      </Button>
    </div>
  )
}

export default function MarketplaceBillingPage() {
  const { user } = useAuth()
  const { isAdmin, loading: roleLoading } = useOrgAdmin()
  const actionLock = useRef(false)
  const [isWorking, setIsWorking] = useState(false)
  const [lastSyncResult, setLastSyncResult] =
    useState<MarketplacePublisherPayoutSyncResult | null>(null)

  const { data, error, mutate, isLoading } = useSWR<MarketplaceBillingStatus>(
    user && isAdmin ? "/api/marketplace/billing/status" : null,
    fetcher,
  )

  const {
    data: pricingData,
    error: pricingError,
    mutate: mutatePricing,
  } = useSWR<{ pricing: MarketplacePartnerPricing[] }>(
    user && isAdmin ? "/api/marketplace/billing/pricing" : null,
    fetcher,
  )

  const pricing: MarketplacePartnerPricing[] = pricingData?.pricing ?? []
  const account = data?.account
  const earnings = data?.earnings
  const assetPayouts = data?.assetPayouts
  const recentAssetPayouts: MarketplaceAssetPayoutRow[] =
    data?.recentAssetPayouts ?? []
  const readyForPayouts = connectReady(account)

  const pendingBadge = useMemo(() => {
    const count = assetPayouts?.pendingPayoutCount ?? 0
    return count > 0 ? count : null
  }, [assetPayouts?.pendingPayoutCount])

  const handleOnboard = async () => {
    if (actionLock.current || !isAdmin || !data) return
    actionLock.current = true
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
      actionLock.current = false
      setIsWorking(false)
    }
  }

  const handleSync = async () => {
    if (actionLock.current || !isAdmin || !data) return
    actionLock.current = true
    setIsWorking(true)
    try {
      await marketplaceApi.syncConnectAccount()
      toast.success("Connect account synced")
      await Promise.allSettled([mutate()])
    } catch (err) {
      toast.error("Sync failed", {
        description: err instanceof Error ? err.message : "Try again",
      })
    } finally {
      actionLock.current = false
      setIsWorking(false)
    }
  }

  const handlePayoutSync = async () => {
    if (!readyForPayouts) {
      toast.error("Complete Stripe Connect onboarding before syncing payouts")
      return
    }
    if (actionLock.current || !isAdmin || !data) return
    actionLock.current = true
    setIsWorking(true)
    try {
      const result = await marketplaceApi.syncPublisherPayouts()
      setLastSyncResult(result.sync)
      const { transferred, failed, pendingReviewed } = result.sync
      if (pendingReviewed === 0) {
        toast.success("No pending asset payouts to sync")
      } else if (transferred > 0) {
        toast.success(
          `Transferred ${transferred} asset payout${transferred === 1 ? "" : "s"}`,
        )
      } else if (failed > 0) {
        toast.error(
          `${failed} payout transfer${failed === 1 ? "" : "s"} failed`,
          {
            description: "Check Stripe Connect status and try again",
          },
        )
      } else {
        toast.message("Pending payouts reviewed", {
          description:
            "Transfers retry when Connect is active and balances settle",
        })
      }
      await Promise.allSettled([mutate()])
    } catch (err) {
      toast.error("Payout sync failed", {
        description: err instanceof Error ? err.message : "Try again",
      })
    } finally {
      actionLock.current = false
      setIsWorking(false)
    }
  }

  if (roleLoading)
    return (
      <AppShell title="Partner billing">
        <p role="status" className="p-6">
          Checking organization permissions…
        </p>
      </AppShell>
    )
  if (!isAdmin) {
    return (
      <AppShell title="Partner billing">
        <div className="mx-auto max-w-lg rounded-lg border bg-card p-6 text-center text-sm text-muted-foreground">
          Admin access is required to manage marketplace billing and payouts.
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title="Partner billing">
      <div
        className="bg-[color:var(--g-canvas)] pb-24 [&_[data-slot=button]]:min-h-11 [&_input]:min-h-11"
        data-composition="operate"
      >
        <GravitrePageHeader
          art="dept-finance"
          title="Partner revenue & payouts"
          description="Connect Stripe, sync pending asset payouts, and manage connector pricing."
          icon={<DollarSign className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" asChild>
                <Link href="/marketplace/assets">
                  <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
                  Marketplace
                </Link>
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link href="/marketplace/publisher/analytics">
                  <TrendingUp className="mr-1.5 h-4 w-4" aria-hidden />
                  Revenue analytics
                </Link>
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link href="/marketplace/submit">Partner submissions</Link>
              </Button>
            </div>
          }
        />

        <div className="mx-auto max-w-3xl space-y-8 px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)] sm:py-5">
          {error ? (
            <WorkSectionErrorCard
              title="Could not refresh billing status"
              onRetry={() => void mutate()}
            />
          ) : null}
          {isLoading && !data ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              Loading billing status...
            </div>
          ) : !data ? null : (
            <>
              <div className="rounded-lg border border-border bg-card p-5 space-y-4">
                <div className="flex items-center gap-2">
                  <CreditCard
                    className="h-4 w-4 text-muted-foreground"
                    aria-hidden
                  />
                  <p className="text-sm font-medium">Stripe Connect</p>
                </div>
                <p className="text-sm text-muted-foreground">
                  Status:{" "}
                  <span className="font-mono text-foreground">
                    {account?.connectStatus ?? "Not reported"}
                  </span>
                  {readyForPayouts
                    ? " · ready for payouts"
                    : " · onboarding required for transfers"}
                </p>
                <div className="flex flex-wrap gap-2">
                  {!readyForPayouts ? (
                    <Button
                      onClick={() => void handleOnboard()}
                      disabled={isWorking}
                      className="gap-2"
                    >
                      {isWorking ? (
                        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                      ) : (
                        <CreditCard className="h-4 w-4" aria-hidden />
                      )}
                      Connect Stripe payouts
                    </Button>
                  ) : null}
                  <Button
                    variant="outline"
                    onClick={() => void handleSync()}
                    disabled={isWorking}
                    className="gap-2"
                  >
                    <RefreshCw className="h-4 w-4" aria-hidden />
                    Sync account
                  </Button>
                </div>
              </div>

              {earnings ? (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {[
                    {
                      label: "Connector gross",
                      value: formatUsd(earnings.grossCents),
                    },
                    {
                      label: "Connector earnings",
                      value: formatUsd(earnings.partnerEarningsCents),
                    },
                    {
                      label: "Connector transferred",
                      value: formatUsd(earnings.transferredCents),
                    },
                    {
                      label: "Active installs",
                      value: String(earnings.activeInstallCount),
                    },
                  ].map((stat) => (
                    <div
                      key={stat.label}
                      className="rounded-md border border-border bg-muted/20 p-4"
                    >
                      <p className="text-xs text-muted-foreground">
                        {stat.label}
                      </p>
                      <p className="mt-1 text-lg font-semibold">{stat.value}</p>
                    </div>
                  ))}
                </div>
              ) : null}

              <div className="rounded-lg border border-border bg-card p-5 space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium">
                      Unified asset payout sync
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Retry Stripe Connect transfers for pending paid asset
                      purchases.
                      {data?.platformFeeBps != null
                        ? ` Creator share: ${100 - data.platformFeeBps / 100}% after ${data.platformFeeBps / 100}% platform fee.`
                        : null}
                    </p>
                  </div>
                  <Button
                    variant="default"
                    size="sm"
                    onClick={() => void handlePayoutSync()}
                    disabled={isWorking || !readyForPayouts}
                    className="gap-2"
                  >
                    {isWorking ? (
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                    ) : (
                      <RefreshCw className="h-4 w-4" aria-hidden />
                    )}
                    Sync pending payouts
                    {pendingBadge ? (
                      <Badge
                        variant="secondary"
                        className="ml-1 px-1.5 py-0 text-[10px]"
                      >
                        {pendingBadge}
                      </Badge>
                    ) : null}
                  </Button>
                </div>

                {!readyForPayouts ? (
                  <div className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/5 p-3 text-sm">
                    <AlertCircle
                      className="mt-0.5 h-4 w-4 shrink-0 text-warning"
                      aria-hidden
                    />
                    <p className="text-muted-foreground">
                      Finish Stripe Connect onboarding before asset payout
                      transfers can run.
                    </p>
                  </div>
                ) : null}

                {assetPayouts && assetPayouts.payoutCount > 0 ? (
                  <>
                    <PayoutTransferHero summary={assetPayouts} />
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                      {[
                        {
                          label: "Asset sales",
                          value: formatUsd(assetPayouts.grossCents),
                        },
                        {
                          label: "Platform fees",
                          value: formatUsd(assetPayouts.platformFeeCents),
                        },
                        {
                          label: "Your share",
                          value: formatUsd(assetPayouts.partnerEarningsCents),
                        },
                        {
                          label: "Transferred",
                          value: formatUsd(assetPayouts.transferredCents),
                        },
                        {
                          label: "Pending transfer",
                          value: formatUsd(assetPayouts.pendingTransferCents),
                        },
                      ].map((stat) => (
                        <div
                          key={stat.label}
                          className="rounded-md border border-border bg-muted/20 p-4"
                        >
                          <p className="text-xs text-muted-foreground">
                            {stat.label}
                          </p>
                          <p className="mt-1 text-lg font-semibold">
                            {stat.value}
                          </p>
                        </div>
                      ))}
                    </div>
                    {(assetPayouts.pendingPayoutCount ?? 0) > 0 ||
                    (assetPayouts.failedPayoutCount ?? 0) > 0 ? (
                      <div className="flex flex-wrap gap-2 text-xs">
                        {(assetPayouts.pendingPayoutCount ?? 0) > 0 ? (
                          <Badge variant="secondary">
                            {assetPayouts.pendingPayoutCount} pending payout(s)
                          </Badge>
                        ) : null}
                        {(assetPayouts.failedPayoutCount ?? 0) > 0 ? (
                          <Badge variant="destructive">
                            {assetPayouts.failedPayoutCount} failed transfer(s)
                          </Badge>
                        ) : null}
                      </div>
                    ) : null}
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No paid asset sales recorded yet.
                  </p>
                )}

                {lastSyncResult ? (
                  <LastSyncResult result={lastSyncResult} />
                ) : null}

                {recentAssetPayouts.length > 0 ? (
                  <AdaptiveDataView className="rounded border border-border">
                    <table className="w-full text-xs">
                      <thead className="bg-muted/50">
                        <tr>
                          <th className="px-3 py-2 text-left font-medium">
                            Asset
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Gross
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Earnings
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Status
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Time
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {recentAssetPayouts.map((row) => (
                          <tr key={row.id} className="border-t border-border">
                            <td className="px-3 py-2">
                              {row.assetSlug ? (
                                <Link
                                  href={`/marketplace/assets/${encodeURIComponent(row.assetSlug)}`}
                                  className="hover:text-primary"
                                >
                                  {row.assetTitle ?? row.assetSlug}
                                </Link>
                              ) : (
                                (row.assetTitle ?? row.assetId ?? "Asset")
                              )}
                            </td>
                            <td className="px-3 py-2 tabular-nums">
                              {formatUsd(row.grossCents)}
                            </td>
                            <td className="px-3 py-2 tabular-nums">
                              {formatUsd(row.partnerEarningsCents)}
                            </td>
                            <td className="px-3 py-2">
                              <Badge variant={payoutStatusVariant(row.status)}>
                                {row.status}
                              </Badge>
                            </td>
                            <td className="px-3 py-2 text-muted-foreground">
                              {row.createdAt
                                ? new Date(row.createdAt).toLocaleString()
                                : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </AdaptiveDataView>
                ) : null}
              </div>

              <div className="space-y-3">
                <h2 className="text-sm font-medium">Connector pricing</h2>
                {pricingError ? (
                  <WorkSectionErrorCard
                    title="Could not refresh connector pricing"
                    onRetry={() => void mutatePricing()}
                  />
                ) : null}
                {!pricingData ? null : pricing.length === 0 ? (
                  <div className="py-2 text-center">
                    <Illustration name="moment-welcome" width={140} className="mx-auto mb-3" />
                    <p className="text-sm text-muted-foreground">
                      Publish a connector to the marketplace before setting
                      pricing.
                    </p>
                  </div>
                ) : (
                  pricing.map((item) => (
                    <PricingRow
                      key={item.registryId}
                      item={item}
                      platformFeeBps={data?.platformFeeBps}
                      onSaved={() => void mutatePricing()}
                    />
                  ))
                )}
              </div>

              {data?.recentUsage && data.recentUsage.length > 0 ? (
                <div className="space-y-2">
                  <h2 className="text-sm font-medium">
                    Recent connector usage
                  </h2>
                  <AdaptiveDataView className="rounded border border-border">
                    <table className="w-full text-xs">
                      <thead className="bg-muted/50">
                        <tr>
                          <th className="px-3 py-2 text-left font-medium">
                            Action
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Earnings
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Transfer
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Time
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.recentUsage.map((row) => (
                          <tr key={row.id} className="border-t border-border">
                            <td className="px-3 py-2 font-mono">
                              {row.action}
                            </td>
                            <td className="px-3 py-2 tabular-nums">
                              {formatUsd(row.partnerEarningsCents)}
                            </td>
                            <td className="px-3 py-2">
                              <Badge variant="outline">
                                {row.transferStatus}
                              </Badge>
                            </td>
                            <td className="px-3 py-2 text-muted-foreground">
                              {row.createdAt
                                ? new Date(row.createdAt).toLocaleString()
                                : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </AdaptiveDataView>
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>
    </AppShell>
  )
}
