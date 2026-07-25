"use client"

import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { AdaptiveDataView } from "@/components/gravitre/adaptive-data-view"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { GridPattern } from "@/components/gravitre/premium-effects"
import { marketplaceApi } from "@/lib/api"
import { fetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { ROI_PAGE_TITLE } from "@/lib/marketplace-outcome-labels"
import {
  ArrowLeft,
  BarChart3,
  DollarSign,
  Plug,
  RefreshCw,
  Sparkles,
  TrendingUp,
} from "lucide-react"
import { toast } from "sonner"
import type {
  MarketplaceAssetPayoutRow,
  MarketplacePublisherEarningsBreakdown,
  MarketplacePublisherRevenueAnalytics,
  MarketplaceTopEarningAsset,
  MarketplaceUsageEvent,
} from "@/types/api"

function formatUsd(cents: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(cents / 100)
}

function formatDate(value?: string | null) {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "—"
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

function transferRate(earnings: MarketplacePublisherEarningsBreakdown) {
  const earned = earnings.partnerEarningsCents
  if (earned <= 0) return 0
  return Math.min(100, (earnings.transferredCents / earned) * 100)
}

function MoneyCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-foreground">{value}</p>
      {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  )
}

function TransferHero({ combined }: { combined: MarketplacePublisherEarningsBreakdown }) {
  const rate = transferRate(combined)
  const pending = combined.pendingTransferCents
  return (
    <div className="rounded-xl border border-border bg-card p-5 md:p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-foreground">Payout transfer rate</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Share of your earnings already transferred via Stripe Connect.
          </p>
        </div>
        <Badge variant={rate >= 90 ? "default" : pending > 0 ? "secondary" : "outline"}>
          {rate.toFixed(1)}% transferred
        </Badge>
      </div>
      <Progress value={rate} className="mb-2 h-3" />
      <div className="flex flex-wrap justify-between gap-2 text-xs text-muted-foreground">
        <span>{formatUsd(combined.transferredCents)} transferred</span>
        <span>{formatUsd(pending)} pending</span>
      </div>
    </div>
  )
}

function RevenueMixBar({
  connectorGross,
  assetGross,
}: {
  connectorGross: number
  assetGross: number
}) {
  const total = connectorGross + assetGross
  if (total <= 0) {
    return (
      <p className="text-sm text-muted-foreground">No gross revenue recorded yet across connector usage or paid assets.</p>
    )
  }
  const connectorPct = Math.round((connectorGross / total) * 100)
  const assetPct = 100 - connectorPct
  return (
    <div className="space-y-3">
      <div className="flex h-3 overflow-hidden rounded-full bg-muted">
        <div className="bg-primary transition-all" style={{ width: `${connectorPct}%` }} title="Connector usage" />
        <div className="bg-success transition-all" style={{ width: `${assetPct}%` }} title="Paid asset sales" />
      </div>
      <div className="grid gap-3 text-sm sm:grid-cols-2">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-primary" aria-hidden />
          <span className="text-muted-foreground">Connector usage</span>
          <span className="ml-auto tabular-nums font-medium">{formatUsd(connectorGross)} · {connectorPct}%</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-success" aria-hidden />
          <span className="text-muted-foreground">Paid asset sales</span>
          <span className="ml-auto tabular-nums font-medium">{formatUsd(assetGross)} · {assetPct}%</span>
        </div>
      </div>
    </div>
  )
}

function TopAssetsTable({ title, rows }: { title: string; rows: MarketplaceTopEarningAsset[] }) {
  if (!rows.length) {
    return (
      <div className="rounded-xl border border-border bg-card p-5">
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
        <p className="mt-2 text-sm text-muted-foreground">No paid asset sales recorded yet.</p>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <h2 className="mb-3 text-sm font-semibold text-foreground">{title}</h2>
      <AdaptiveDataView className="border-0">
        <table className="w-full text-sm">
          <thead className="text-xs text-muted-foreground">
            <tr>
              <th className="pb-2 text-left font-medium">Asset</th>
              <th className="pb-2 text-left font-medium">Type</th>
              <th className="pb-2 text-left font-medium">Sales</th>
              <th className="pb-2 text-left font-medium">Gross</th>
              <th className="pb-2 text-left font-medium">Your share</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.assetId} className="border-t border-border">
                <td className="py-2">
                  {row.slug ? (
                    <Link
                      href={`/marketplace/assets/${encodeURIComponent(row.slug)}`}
                      className="text-foreground hover:text-primary"
                    >
                      {row.title ?? row.slug}
                    </Link>
                  ) : (
                    <span className="text-muted-foreground">{row.title ?? row.assetId}</span>
                  )}
                </td>
                <td className="py-2 capitalize text-muted-foreground">{row.assetType?.replace(/_/g, " ") ?? "—"}</td>
                <td className="py-2 tabular-nums">{row.saleCount}</td>
                <td className="py-2 tabular-nums">{formatUsd(row.grossCents)}</td>
                <td className="py-2 tabular-nums">{formatUsd(row.partnerEarningsCents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </AdaptiveDataView>
    </div>
  )
}

function payoutStatusVariant(status: string) {
  if (status === "transferred") return "default"
  if (status === "failed") return "destructive"
  return "secondary"
}

function RecentPayoutsList({ rows }: { rows: MarketplaceAssetPayoutRow[] }) {
  if (!rows.length) {
    return <p className="text-sm text-muted-foreground">No asset payouts yet.</p>
  }
  return (
    <ul className="space-y-2 text-sm">
      {rows.map((row) => (
        <li key={row.id} className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate">{row.assetTitle ?? row.assetSlug ?? "Asset"}</p>
            <p className="text-xs text-muted-foreground">{formatDate(row.createdAt)}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <span className="tabular-nums">{formatUsd(row.partnerEarningsCents)}</span>
            <Badge variant={payoutStatusVariant(row.status)}>{row.status}</Badge>
          </div>
        </li>
      ))}
    </ul>
  )
}

function RecentUsageList({ rows }: { rows: MarketplaceUsageEvent[] }) {
  if (!rows.length) {
    return <p className="text-sm text-muted-foreground">No connector usage events yet.</p>
  }
  return (
    <ul className="space-y-2 text-sm">
      {rows.map((row) => (
        <li key={row.id} className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate font-mono text-xs">{row.action}</p>
            <p className="text-xs text-muted-foreground">{formatDate(row.createdAt)}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <span className="tabular-nums">{formatUsd(row.partnerEarningsCents)}</span>
            <Badge variant="outline">{row.transferStatus}</Badge>
          </div>
        </li>
      ))}
    </ul>
  )
}

function EmptyRevenueState() {
  return (
    <div className="rounded-xl border border-dashed border-border bg-card/50 p-8 text-center">
      <Sparkles className="mx-auto mb-3 h-8 w-8 text-muted-foreground/70" aria-hidden />
      <p className="text-sm font-medium text-foreground">No publisher revenue yet</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
        Onboard as a publisher, list paid assets or connector pricing, and sync payouts once sales occur.
      </p>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        <Button size="sm" asChild>
          <Link href="/marketplace/publisher">Publisher profile</Link>
        </Button>
        <Button size="sm" variant="outline" asChild>
          <Link href="/marketplace/billing">Billing setup</Link>
        </Button>
      </div>
    </div>
  )
}

function hasAnyRevenue(data: MarketplacePublisherRevenueAnalytics) {
  const combined = data.earnings.combined
  return (
    combined.grossCents > 0 ||
    data.adoption.publishedAssets > 0 ||
    data.topAssetsByEarnings.length > 0 ||
    data.recentAssetPayouts.length > 0 ||
    data.recentUsageEvents.length > 0
  )
}

export default function MarketplacePublisherAnalyticsPage() {
  const { user } = useAuth()
  const { isAdmin } = useOrgAdmin()

  const { data: me } = useSWR(user ? "/api/auth/me" : null, fetcher)
  const isPlatformAdmin = Boolean((me as { platformAdmin?: boolean } | undefined)?.platformAdmin)

  const { data: publisherProfile } = useSWR(
    user && isAdmin ? "marketplace-publisher-profile" : null,
    () => marketplaceApi.getPublisherProfile(),
  )

  const { data, error, isLoading, mutate } = useSWR(
    user && isAdmin ? "marketplace-publisher-revenue-analytics" : null,
    () => marketplaceApi.publisherRevenueAnalytics(),
  )

  const handlePayoutSync = async () => {
    try {
      const result = await marketplaceApi.syncPublisherPayouts()
      const { transferred, failed, pendingReviewed } = result.sync
      if (pendingReviewed === 0) {
        toast.success("No pending asset payouts to sync")
      } else if (transferred > 0) {
        toast.success(`Transferred ${transferred} payout${transferred === 1 ? "" : "s"}`)
      } else if (failed > 0) {
        toast.error(`${failed} payout transfer${failed === 1 ? "" : "s"} failed`)
      } else {
        toast.message("Pending payouts reviewed")
      }
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Payout sync failed")
    }
  }

  if (!isAdmin) {
    return (
      <AppShell title="Publisher revenue">
        <div className="mx-auto max-w-lg rounded-lg border bg-card p-6 text-center text-sm text-muted-foreground">
          Admin access is required to view publisher revenue analytics.
        </div>
      </AppShell>
    )
  }

  const combined = data?.earnings.combined
  const connector = data?.earnings.connectorUsage
  const assetSales = data?.earnings.assetSales
  const publisherName = publisherProfile?.publisher?.displayName

  return (
    <AppShell title="Publisher revenue">
      <div className="relative shrink-0 overflow-hidden rounded-2xl border bg-card/40 p-6 md:p-8">
        <GridPattern className="opacity-40" />
        <div className="relative mx-auto max-w-5xl space-y-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <Button variant="ghost" size="sm" asChild className="-ml-2 mb-2">
                <Link href="/marketplace/assets">
                  <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
                  Marketplace
                </Link>
              </Button>
              <h1 className="flex items-center gap-2 text-xl font-semibold">
                <TrendingUp className="h-5 w-5 text-primary" aria-hidden />
                Publisher revenue analytics
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {publisherName
                  ? `${publisherName} — connector usage and paid unified asset sales.`
                  : "Combined connector usage and paid unified asset sales for your organization."}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" asChild>
                <Link href="/marketplace/analytics/roi">{ROI_PAGE_TITLE}</Link>
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link href="/marketplace/billing">Billing & payouts</Link>
              </Button>
              <Button variant="outline" size="sm" onClick={() => void handlePayoutSync()}>
                <RefreshCw className="mr-1.5 h-4 w-4" aria-hidden />
                Sync payouts
              </Button>
            </div>
          </div>

          {isLoading && !data ? (
            <div className="space-y-4">
              <Skeleton className="h-32 rounded-xl" />
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {Array.from({ length: 4 }).map((_, index) => (
                  <Skeleton key={index} className="h-24 rounded-xl" />
                ))}
              </div>
            </div>
          ) : error ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
              Could not load publisher revenue analytics.
            </div>
          ) : data && combined ? (
            hasAnyRevenue(data) ? (
              <>
                <TransferHero combined={combined} />

                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                  <MoneyCard label="Total gross" value={formatUsd(combined.grossCents)} />
                  <MoneyCard label="Platform fees" value={formatUsd(combined.platformFeeCents)} />
                  <MoneyCard label="Your earnings" value={formatUsd(combined.partnerEarningsCents)} />
                  <MoneyCard label="Transferred" value={formatUsd(combined.transferredCents)} />
                  <MoneyCard label="Pending transfer" value={formatUsd(combined.pendingTransferCents)} />
                </div>

                <div className="rounded-xl border border-border bg-card p-5">
                  <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold">
                    <BarChart3 className="h-4 w-4 text-primary" aria-hidden />
                    Revenue mix
                  </h2>
                  <p className="mb-4 text-xs text-muted-foreground">Gross revenue split between connector usage and paid asset sales.</p>
                  <RevenueMixBar
                    connectorGross={connector?.grossCents ?? 0}
                    assetGross={assetSales?.grossCents ?? 0}
                  />
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="rounded-xl border border-border bg-card p-5 space-y-3">
                    <h2 className="flex items-center gap-2 text-sm font-semibold">
                      <Plug className="h-4 w-4 text-primary" aria-hidden />
                      Connector usage revenue
                    </h2>
                    {connector ? (
                      <dl className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <dt className="text-muted-foreground">Gross</dt>
                          <dd className="font-medium tabular-nums">{formatUsd(connector.grossCents)}</dd>
                        </div>
                        <div>
                          <dt className="text-muted-foreground">Your share</dt>
                          <dd className="font-medium tabular-nums">{formatUsd(connector.partnerEarningsCents)}</dd>
                        </div>
                        <div>
                          <dt className="text-muted-foreground">Usage events</dt>
                          <dd className="font-medium tabular-nums">{connector.usageEventCount ?? 0}</dd>
                        </div>
                        <div>
                          <dt className="text-muted-foreground">Active installs</dt>
                          <dd className="font-medium tabular-nums">{connector.activeInstallCount ?? 0}</dd>
                        </div>
                      </dl>
                    ) : null}
                  </div>

                  <div className="rounded-xl border border-border bg-card p-5 space-y-3">
                    <h2 className="flex items-center gap-2 text-sm font-semibold">
                      <DollarSign className="h-4 w-4 text-primary" aria-hidden />
                      Paid asset sales
                    </h2>
                    {assetSales ? (
                      <dl className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <dt className="text-muted-foreground">Gross</dt>
                          <dd className="font-medium tabular-nums">{formatUsd(assetSales.grossCents)}</dd>
                        </div>
                        <div>
                          <dt className="text-muted-foreground">Your share</dt>
                          <dd className="font-medium tabular-nums">{formatUsd(assetSales.partnerEarningsCents)}</dd>
                        </div>
                        <div>
                          <dt className="text-muted-foreground">Paid sales</dt>
                          <dd className="font-medium tabular-nums">{assetSales.payoutCount ?? 0}</dd>
                        </div>
                        <div>
                          <dt className="text-muted-foreground">Pending transfer</dt>
                          <dd className="font-medium tabular-nums">{formatUsd(assetSales.pendingTransferCents)}</dd>
                        </div>
                      </dl>
                    ) : null}
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <MoneyCard label="Published assets" value={String(data.adoption.publishedAssets)} />
                  <MoneyCard label="Asset installs" value={String(data.adoption.totalInstalls)} />
                  <MoneyCard label="Usage events" value={String(data.adoption.usageEventCount)} />
                  <MoneyCard label="Paid sales" value={String(data.adoption.paidSaleCount)} />
                </div>

                <TopAssetsTable title="Top earning assets (your org)" rows={data.topAssetsByEarnings} />

                {isPlatformAdmin && data.platformTopAssets?.length ? (
                  <TopAssetsTable title="Platform top earning assets" rows={data.platformTopAssets} />
                ) : null}

                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="rounded-xl border border-border bg-card p-5">
                    <h2 className="mb-3 text-sm font-semibold">Recent asset payouts</h2>
                    <RecentPayoutsList rows={data.recentAssetPayouts} />
                  </div>
                  <div className="rounded-xl border border-border bg-card p-5">
                    <h2 className="mb-3 text-sm font-semibold">Recent connector usage</h2>
                    <RecentUsageList rows={data.recentUsageEvents} />
                  </div>
                </div>
              </>
            ) : (
              <EmptyRevenueState />
            )
          ) : null}
        </div>
      </div>
    </AppShell>
  )
}
