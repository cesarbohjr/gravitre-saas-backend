"use client"

import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { marketplaceApi } from "@/lib/api"
import { fetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import {
  ArrowLeft,
  BarChart3,
  DollarSign,
  Loader2,
  RefreshCw,
  TrendingUp,
} from "lucide-react"
import { toast } from "sonner"
import type { MarketplaceTopEarningAsset } from "@/types/api"

function formatUsd(cents: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(cents / 100)
}

function MoneyCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-foreground">{value}</p>
    </div>
  )
}

function TopAssetsTable({
  title,
  rows,
}: {
  title: string
  rows: MarketplaceTopEarningAsset[]
}) {
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
      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[620px]">
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
      </div>
    </div>
  )
}

export default function MarketplacePublisherAnalyticsPage() {
  const { user } = useAuth()
  const role = user?.role
  const isAdmin = role === "admin" || role === "owner"
  const { data: me } = useSWR(user ? "/api/auth/me" : null, fetcher)
  const isPlatformAdmin = Boolean((me as { platformAdmin?: boolean } | undefined)?.platformAdmin)

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

  return (
    <AppShell title="Publisher revenue">
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <Button variant="ghost" size="sm" asChild className="-ml-2 mb-2">
              <Link href="/marketplace">
                <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
                Marketplace
              </Link>
            </Button>
            <h1 className="flex items-center gap-2 text-xl font-semibold">
              <TrendingUp className="h-5 w-5 text-primary" aria-hidden />
              Publisher revenue analytics
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Combined connector usage and paid unified asset sales for your organization.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" asChild>
              <Link href="/marketplace/analytics">Org adoption analytics</Link>
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
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-24 rounded-xl" />
            ))}
          </div>
        ) : error ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            Could not load publisher revenue analytics.
          </div>
        ) : data && combined ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <MoneyCard label="Total gross" value={formatUsd(combined.grossCents)} />
              <MoneyCard label="Your earnings" value={formatUsd(combined.partnerEarningsCents)} />
              <MoneyCard label="Transferred" value={formatUsd(combined.transferredCents)} />
              <MoneyCard label="Pending transfer" value={formatUsd(combined.pendingTransferCents)} />
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-xl border border-border bg-card p-5 space-y-3">
                <h2 className="flex items-center gap-2 text-sm font-semibold">
                  <BarChart3 className="h-4 w-4 text-primary" aria-hidden />
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
                {data.recentAssetPayouts.length ? (
                  <ul className="space-y-2 text-sm">
                    {data.recentAssetPayouts.map((row) => (
                      <li key={row.id} className="flex items-center justify-between gap-2">
                        <span className="truncate">{row.assetTitle ?? row.assetSlug ?? "Asset"}</span>
                        <span className="shrink-0 tabular-nums text-muted-foreground">
                          {formatUsd(row.partnerEarningsCents)} · {row.status}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">No asset payouts yet.</p>
                )}
              </div>

              <div className="rounded-xl border border-border bg-card p-5">
                <h2 className="mb-3 text-sm font-semibold">Recent connector usage</h2>
                {data.recentUsageEvents.length ? (
                  <ul className="space-y-2 text-sm">
                    {data.recentUsageEvents.map((row) => (
                      <li key={row.id} className="flex items-center justify-between gap-2">
                        <span className="truncate font-mono text-xs">{row.action}</span>
                        <span className="shrink-0 tabular-nums text-muted-foreground">
                          {formatUsd(row.partnerEarningsCents)} · {row.transferStatus}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">No usage events yet.</p>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            Loading revenue analytics...
          </div>
        )}
      </div>
    </AppShell>
  )
}
