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
import { useAuth } from "@/lib/auth-context"
import { cn } from "@/lib/utils"
import {
  ArrowLeft,
  BarChart3,
  Clock,
  Package,
  Sparkles,
  TrendingUp,
} from "lucide-react"
import type { MarketplaceRoiAssetRow, MarketplaceRoiSummary } from "@/types/api"
import {
  ADOPTED_ESTIMATE_HOURS_LABEL,
  CATALOG_ESTIMATE_HOURS_LABEL,
  ESTIMATED_HOURS_SAVED_LABEL,
  ROI_METHODOLOGY,
  ROI_PAGE_TITLE,
} from "@/lib/marketplace-outcome-labels"

function formatHours(value: number) {
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })}h`
}

function formatDate(value?: string | null) {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "—"
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

function StatCard({
  label,
  value,
  hint,
  icon: Icon,
}: {
  label: string
  value: string
  hint?: string
  icon: typeof Clock
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="mb-3 flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
        <Icon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
      </div>
      <p className="text-3xl font-semibold tabular-nums text-foreground">{value}</p>
      {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  )
}

function RealizationHero({ roi }: { roi: MarketplaceRoiSummary }) {
  const rate = Math.min(100, Math.max(0, roi.realizationRate))
  return (
    <div className="rounded-xl border border-border bg-card p-5 md:p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-foreground">Adoption rate (estimates)</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Share of catalog estimates from active installs that recorded at least one adoption event (still an estimate,
            not measured time-on-task).
          </p>
        </div>
        <Badge variant={rate >= 75 ? "default" : rate >= 25 ? "secondary" : "outline"}>
          {rate.toFixed(1)}% adopted
        </Badge>
      </div>
      <Progress value={rate} className="mb-2 h-3" />
      <div className="flex flex-wrap justify-between gap-2 text-xs text-muted-foreground">
        <span>{formatHours(roi.totalRealizedHoursSaved)} {ADOPTED_ESTIMATE_HOURS_LABEL.toLowerCase()}</span>
        <span>{formatHours(roi.totalEstimatedHoursSaved)} {CATALOG_ESTIMATE_HOURS_LABEL.toLowerCase()}</span>
      </div>
    </div>
  )
}

function AssetRealizationBar({ estimated, realized }: { estimated: number; realized: number }) {
  const pct = estimated > 0 ? Math.min(100, (realized / estimated) * 100) : 0
  return (
    <div className="min-w-[120px] space-y-1">
      <Progress value={pct} className="h-1.5" />
      <p className="text-[11px] tabular-nums text-muted-foreground">
        {formatHours(realized)} / {formatHours(estimated)}
      </p>
    </div>
  )
}

function RoiAssetTable({ rows }: { rows: MarketplaceRoiAssetRow[] }) {
  if (!rows.length) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-card/50 p-8 text-center">
        <Sparkles className="mx-auto mb-3 h-8 w-8 text-muted-foreground/70" aria-hidden />
        <p className="text-sm font-medium text-foreground">No ROI data yet</p>
        <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
          Install marketplace assets with estimated hours saved, then run agents or workflows to record adoption
          events.
        </p>
        <Button size="sm" className="mt-4" asChild>
          <Link href="/marketplace/assets">Browse catalog</Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <h2 className="mb-3 text-sm font-semibold text-foreground">By installed asset</h2>
      <AdaptiveDataView className="rounded-2xl border border-border/70">
        <table className="w-full text-sm">
          <thead className="text-xs text-muted-foreground">
            <tr>
              <th className="pb-2 text-left font-medium">Asset</th>
              <th className="pb-2 text-left font-medium">Outcome</th>
              <th className="pb-2 text-left font-medium">Use case</th>
              <th className="pb-2 text-left font-medium">Installed</th>
              <th className="pb-2 text-left font-medium">Events</th>
              <th className="pb-2 text-left font-medium">{ESTIMATED_HOURS_SAVED_LABEL}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const active = row.usageEvents > 0
              return (
                <tr key={row.installId} className="border-t border-border">
                  <td className="py-3 pr-3">
                    {row.slug ? (
                      <Link
                        href={`/marketplace/assets/${encodeURIComponent(row.slug)}`}
                        className="font-medium text-foreground hover:text-primary"
                      >
                        {row.title ?? row.slug}
                      </Link>
                    ) : (
                      <span className="text-muted-foreground">{row.title ?? row.assetId}</span>
                    )}
                  </td>
                  <td className="max-w-[180px] py-3 pr-3 text-muted-foreground">
                    {row.businessOutcome ?? "—"}
                  </td>
                  <td className="max-w-[160px] py-3 pr-3 text-muted-foreground">{row.useCase ?? "—"}</td>
                  <td className="py-3 pr-3 tabular-nums text-muted-foreground">{formatDate(row.installedAt)}</td>
                  <td className="py-3 pr-3">
                    <Badge variant={active ? "secondary" : "outline"}>{row.usageEvents}</Badge>
                  </td>
                  <td className="py-3">
                    <AssetRealizationBar
                      estimated={row.estimatedHoursSaved}
                      realized={row.realizedHoursSaved}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </AdaptiveDataView>
    </div>
  )
}

export default function MarketplaceRoiDashboardPage() {
  const { user } = useAuth()
  const role = user?.role
  const isAdmin = role === "admin" || role === "owner"

  const { data: roi, error, isLoading } = useSWR(
    user && isAdmin ? "marketplace-analytics-roi-dashboard" : null,
    () => marketplaceApi.analyticsRoi({ limit: 50 }),
  )

  if (!isAdmin) {
    return (
      <AppShell title={ROI_PAGE_TITLE}>
        <div className="mx-auto max-w-lg rounded-lg border border-border bg-card p-6 text-center text-sm text-muted-foreground">
          Admin access is required to view marketplace ROI.
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title={ROI_PAGE_TITLE}>
      <div className="relative overflow-hidden rounded-2xl border bg-card/40 p-6 md:p-8">
        <GridPattern className="opacity-40" />
        <div className="relative space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="flex items-center gap-2 text-xl font-semibold text-foreground">
                <TrendingUp className="h-5 w-5 text-primary" aria-hidden />
                {ROI_PAGE_TITLE}
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">{ROI_METHODOLOGY}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" asChild>
                <Link href="/marketplace/analytics">
                  <BarChart3 className="mr-1.5 h-4 w-4" aria-hidden />
                  Adoption analytics
                </Link>
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link href="/marketplace">
                  <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
                  Marketplace home
                </Link>
              </Button>
            </div>
          </div>

          {isLoading && !roi ? (
            <div className="space-y-4">
              <Skeleton className="h-32 rounded-xl" />
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {Array.from({ length: 4 }).map((_, index) => (
                  <Skeleton key={index} className="h-28 rounded-xl" />
                ))}
              </div>
              <Skeleton className="h-64 rounded-xl" />
            </div>
          ) : error ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
              Could not load ROI summary.
            </div>
          ) : roi ? (
            <>
              <RealizationHero roi={roi} />
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard
                  label="Active installs"
                  value={roi.activeInstalls.toLocaleString()}
                  icon={Package}
                />
                <StatCard
                  label="Assets with usage"
                  value={roi.assetsWithUsage.toLocaleString()}
                  hint={`${roi.totalUsageEvents.toLocaleString()} total events`}
                  icon={BarChart3}
                />
                <StatCard
                  label={CATALOG_ESTIMATE_HOURS_LABEL}
                  value={formatHours(roi.totalEstimatedHoursSaved)}
                  icon={Clock}
                />
                <StatCard
                  label={ADOPTED_ESTIMATE_HOURS_LABEL}
                  value={formatHours(roi.totalRealizedHoursSaved)}
                  icon={TrendingUp}
                />
              </div>
              <RoiAssetTable rows={roi.byAsset} />
              {roi.byAsset.some((row) => row.estimatedHoursSaved <= 0) ? (
                <p className={cn("text-xs text-muted-foreground")}>
                  Assets without {ESTIMATED_HOURS_SAVED_LABEL.toLowerCase()} metadata still appear when installed but
                  contribute zero to totals until catalog metadata is updated.
                </p>
              ) : null}
            </>
          ) : null}
        </div>
      </div>
    </AppShell>
  )
}
