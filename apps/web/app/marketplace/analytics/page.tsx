"use client"

import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitreMetric,
  GravitrePageHeader,
  GravitreSurface,
} from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { ArrowLeft, BarChart3, Clock, Copy, Download, Package, Star, TrendingUp } from "lucide-react"
import {
  ADOPTED_ESTIMATE_HOURS_LABEL,
  CATALOG_ESTIMATE_HOURS_LABEL,
  ADOPTION_RATE_ESTIMATE_LABEL,
  ROI_METHODOLOGY,
  ROI_PAGE_TITLE,
} from "@/lib/marketplace-outcome-labels"

function TopAssetsTable({
  rows,
}: {
  rows: { assetId: string; slug?: string | null; title?: string | null; usageEvents: number }[]
}) {
  if (!rows.length) return null
  return (
    <GravitreSurface className="lg:col-span-3">
      <h2 className="mb-3 text-sm font-semibold text-foreground">Top assets by usage</h2>
      <ul className="space-y-2 text-sm">
        {rows.map((row) => (
          <li key={row.assetId} className="flex items-center justify-between gap-2">
            {row.slug ? (
              <Link
                href={`/marketplace/assets/${encodeURIComponent(row.slug)}`}
                className="truncate text-foreground hover:text-primary"
              >
                {row.title ?? row.slug}
              </Link>
            ) : (
              <span className="truncate text-muted-foreground">{row.title ?? row.assetId}</span>
            )}
            <span className="shrink-0 tabular-nums text-muted-foreground">{row.usageEvents}</span>
          </li>
        ))}
      </ul>
    </GravitreSurface>
  )
}

function FacetTable({ title, rows }: { title: string; rows: { key: string; count: number }[] }) {
  if (!rows.length) return null
  return (
    <GravitreSurface>
      <h2 className="mb-3 text-sm font-semibold text-foreground">{title}</h2>
      <ul className="space-y-2 text-sm">
        {rows.slice(0, 8).map((row) => (
          <li key={row.key} className="flex items-center justify-between gap-2 text-muted-foreground">
            <span className="truncate capitalize">{row.key.replace(/_/g, " ")}</span>
            <span className="tabular-nums">{row.count}</span>
          </li>
        ))}
      </ul>
    </GravitreSurface>
  )
}

export default function MarketplaceAnalyticsPage() {
  const { user } = useAuth()
  const { isAdmin } = useOrgAdmin()

  const { data, error, isLoading } = useSWR(
    user && isAdmin ? "marketplace-analytics" : null,
    () => marketplaceApi.analyticsSummary(),
  )
  const { data: roi, isLoading: roiLoading } = useSWR(
    user && isAdmin ? "marketplace-analytics-roi" : null,
    () => marketplaceApi.analyticsRoi(),
  )

  if (!isAdmin) {
    return (
      <AppShell title="Marketplace analytics">
        <div className="bg-[color:var(--g-canvas)] px-[var(--np-page-pad-sm)] py-6 sm:px-[var(--np-page-pad)]">
          <GravitreSurface className="mx-auto max-w-lg text-center text-sm text-muted-foreground">
            Admin access is required to view marketplace analytics.
          </GravitreSurface>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title="Marketplace analytics">
      <div className="relative shrink-0 bg-[color:var(--g-canvas)]">
        <GravitrePageHeader
          eyebrow="Gravitre Marketplace"
          title="Marketplace analytics"
          description="Catalog adoption and your organization's install activity."
          icon={<BarChart3 className="h-5 w-5" />}
          actions={
            <Button variant="outline" size="sm" asChild>
              <Link href="/marketplace/assets">
                <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
                Marketplace home
              </Link>
            </Button>
          }
        />

        <div className="space-y-6 px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)] sm:py-5">
          {isLoading && !data ? (
            <div className="grid gap-[var(--np-kpi-gap)] sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <Skeleton key={index} className="h-28 rounded-[var(--np-radius-lg)]" />
              ))}
            </div>
          ) : error ? (
            <GravitreSurface className="border-destructive/30 bg-destructive/5 text-sm text-destructive">
              Could not load analytics summary.
            </GravitreSurface>
          ) : data ? (
            <>
              <div className="grid gap-[var(--np-kpi-gap)] sm:grid-cols-2 lg:grid-cols-3">
                <GravitreMetric
                  label="Catalog assets"
                  value={data.catalog.totalAssets.toLocaleString()}
                  icon={<Package className="h-4 w-4" />}
                />
                <GravitreMetric
                  label="Global installs"
                  value={data.catalog.totalInstallCount.toLocaleString()}
                  icon={<Download className="h-4 w-4" />}
                />
                <GravitreMetric
                  label="Global clones"
                  value={data.catalog.totalCloneCount.toLocaleString()}
                  icon={<Copy className="h-4 w-4" />}
                />
                <GravitreMetric
                  label="Your active installs"
                  value={data.org.activeInstalls.toLocaleString()}
                  icon={<Package className="h-4 w-4" />}
                />
                <GravitreMetric
                  label="Your saved assets"
                  value={data.org.savedAssets.toLocaleString()}
                  icon={<Star className="h-4 w-4" />}
                />
                <GravitreMetric
                  label="Your reviews"
                  value={data.org.reviewsSubmitted.toLocaleString()}
                  icon={<Star className="h-4 w-4" />}
                />
                <GravitreMetric
                  label="Usage events"
                  value={(data.org.usageEvents ?? 0).toLocaleString()}
                  icon={<BarChart3 className="h-4 w-4" />}
                />
              </div>
              <div className="grid gap-[var(--np-kpi-gap)] lg:grid-cols-3">
                <FacetTable title="By department" rows={data.catalog.byDepartment} />
                <FacetTable title="By category" rows={data.catalog.byCategory} />
                <FacetTable title="By asset type" rows={data.catalog.byAssetType} />
              </div>
              <TopAssetsTable rows={data.org.topAssetsByUsage ?? []} />
              <GravitreSurface>
                <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold text-foreground">
                      <TrendingUp className="h-4 w-4 text-primary" aria-hidden />
                      {ROI_PAGE_TITLE}
                    </h2>
                    <p className="text-xs text-muted-foreground">{ROI_METHODOLOGY}</p>
                  </div>
                  <Button variant="outline" size="sm" asChild>
                    <Link href="/intelligence/reports">Open ROI reports</Link>
                  </Button>
                </div>
                {roiLoading && !roi ? (
                  <Skeleton className="h-24 w-full rounded-[var(--np-radius-md)]" />
                ) : roi ? (
                  <>
                    <div className="mb-4 grid gap-[var(--np-kpi-gap)] sm:grid-cols-3">
                      <GravitreMetric
                        label={CATALOG_ESTIMATE_HOURS_LABEL}
                        value={roi.totalEstimatedHoursSaved.toLocaleString()}
                        icon={<Clock className="h-4 w-4" />}
                      />
                      <GravitreMetric
                        label={ADOPTED_ESTIMATE_HOURS_LABEL}
                        value={roi.totalRealizedHoursSaved.toLocaleString()}
                        icon={<TrendingUp className="h-4 w-4" />}
                      />
                      <GravitreMetric
                        label={ADOPTION_RATE_ESTIMATE_LABEL}
                        value={roi.realizationRate.toLocaleString()}
                        icon={<BarChart3 className="h-4 w-4" />}
                      />
                    </div>
                    {roi.byAsset.length ? (
                      <p className="text-sm text-muted-foreground">
                        {roi.byAsset.length} installed asset{roi.byAsset.length === 1 ? "" : "s"} with ROI metadata ·{" "}
                        {roi.assetsWithUsage} with usage events
                      </p>
                    ) : (
                      <p className="text-sm text-muted-foreground">No active installs with ROI metadata yet.</p>
                    )}
                  </>
                ) : null}
              </GravitreSurface>
            </>
          ) : null}
        </div>
      </div>
    </AppShell>
  )
}
