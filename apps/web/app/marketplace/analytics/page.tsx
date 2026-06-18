"use client"

import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { GridPattern } from "@/components/gravitre/premium-effects"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { ArrowLeft, BarChart3, Copy, Download, Package, Star } from "lucide-react"

function StatCard({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: number
  icon: typeof Package
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
        <Icon className="h-4 w-4 text-muted-foreground" aria-hidden />
      </div>
      <p className="text-3xl font-semibold tabular-nums text-foreground">{value.toLocaleString()}</p>
    </div>
  )
}

function FacetTable({ title, rows }: { title: string; rows: { key: string; count: number }[] }) {
  if (!rows.length) return null
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <h2 className="mb-3 text-sm font-semibold text-foreground">{title}</h2>
      <ul className="space-y-2 text-sm">
        {rows.slice(0, 8).map((row) => (
          <li key={row.key} className="flex items-center justify-between gap-2 text-muted-foreground">
            <span className="truncate capitalize">{row.key.replace(/_/g, " ")}</span>
            <span className="tabular-nums">{row.count}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function MarketplaceAnalyticsPage() {
  const { user } = useAuth()
  const role = user?.role
  const isAdmin = role === "admin" || role === "owner"

  const { data, error, isLoading } = useSWR(
    user && isAdmin ? "marketplace-analytics" : null,
    () => marketplaceApi.analyticsSummary(),
  )

  if (!isAdmin) {
    return (
      <AppShell title="Marketplace analytics">
        <div className="mx-auto max-w-lg rounded-lg border border-border bg-card p-6 text-center text-sm text-muted-foreground">
          Admin access is required to view marketplace analytics.
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title="Marketplace analytics">
      <div className="relative overflow-hidden rounded-2xl border bg-card/40 p-6 md:p-8">
        <GridPattern className="opacity-40" />
        <div className="relative space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="flex items-center gap-2 text-xl font-semibold text-foreground">
                <BarChart3 className="h-5 w-5 text-primary" aria-hidden />
                Marketplace analytics
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Catalog adoption and your organization&apos;s install activity.
              </p>
            </div>
            <Button variant="outline" size="sm" asChild>
              <Link href="/marketplace">
                <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
                Marketplace home
              </Link>
            </Button>
          </div>

          {isLoading && !data ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <Skeleton key={index} className="h-28 rounded-xl" />
              ))}
            </div>
          ) : error ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
              Could not load analytics summary.
            </div>
          ) : data ? (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <StatCard label="Catalog assets" value={data.catalog.totalAssets} icon={Package} />
                <StatCard label="Global installs" value={data.catalog.totalInstallCount} icon={Download} />
                <StatCard label="Global clones" value={data.catalog.totalCloneCount} icon={Copy} />
                <StatCard label="Your active installs" value={data.org.activeInstalls} icon={Package} />
                <StatCard label="Your saved assets" value={data.org.savedAssets} icon={Star} />
                <StatCard label="Your reviews" value={data.org.reviewsSubmitted} icon={Star} />
              </div>
              <div className="grid gap-4 lg:grid-cols-3">
                <FacetTable title="By department" rows={data.catalog.byDepartment} />
                <FacetTable title="By category" rows={data.catalog.byCategory} />
                <FacetTable title="By asset type" rows={data.catalog.byAssetType} />
              </div>
            </>
          ) : null}
        </div>
      </div>
    </AppShell>
  )
}
