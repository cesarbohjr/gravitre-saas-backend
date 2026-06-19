"use client"

import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { CategoryIconChip } from "@/components/marketplace/category-icon-chip"
import type { AssetCategory } from "@/lib/marketplace-category-icons"
import { AssetSaveButton } from "@/components/marketplace/asset-save-button"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { ArrowLeft, Bookmark, ChevronRight, Star } from "lucide-react"

export default function MarketplaceSavedPage() {
  const { user } = useAuth()
  const { data, error, isLoading, mutate } = useSWR(user ? "marketplace-saves-page" : null, () =>
    marketplaceApi.listSaves({ limit: 100 }),
  )

  const saves = data?.saves ?? []

  return (
    <AppShell title="Saved assets">
      <div className="mx-auto max-w-4xl space-y-6 p-6">
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link href="/marketplace/assets">
            <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
            Catalog
          </Link>
        </Button>

        <header>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <Bookmark className="h-5 w-5 text-primary" aria-hidden />
            Saved assets
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Assets you bookmarked from the unified marketplace catalog.
          </p>
        </header>

        {isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-36 rounded-xl" />
            ))}
          </div>
        ) : error ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            Could not load saved assets.
          </div>
        ) : saves.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border px-6 py-12 text-center">
            <p className="text-sm text-muted-foreground">No saved assets yet.</p>
            <Button className="mt-4" asChild>
              <Link href="/marketplace/assets">Browse catalog</Link>
            </Button>
          </div>
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2">
            {saves.map((entry) => {
              const asset = entry.asset
              if (!asset) return null
              return (
                <li
                  key={entry.id}
                  className="flex flex-col rounded-xl border border-border bg-card p-4 shadow-sm"
                >
                  <div className="mb-3 flex items-start justify-between gap-2">
                    <Link
                      href={`/marketplace/assets/${encodeURIComponent(asset.slug)}`}
                      className="flex min-w-0 flex-1 items-center gap-3"
                    >
                      <CategoryIconChip
                        assetType={asset.assetType as AssetCategory}
                        department={asset.department}
                        size="sm"
                      />
                      <div className="min-w-0">
                        <h2 className="font-semibold leading-tight truncate">{asset.title}</h2>
                        <p className="text-xs text-muted-foreground truncate">
                          {asset.department ?? asset.assetType.replace(/_/g, " ")}
                        </p>
                      </div>
                    </Link>
                    <AssetSaveButton slug={asset.slug} assetId={asset.id} size="icon" />
                  </div>
                  {asset.description ? (
                    <p className="mb-3 line-clamp-2 flex-1 text-sm text-muted-foreground">
                      {asset.description}
                    </p>
                  ) : (
                    <div className="flex-1" />
                  )}
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      {asset.installed ? <Badge variant="secondary">Installed</Badge> : null}
                      {asset.averageRating != null ? (
                        <span className="inline-flex items-center gap-0.5 text-[11px] text-muted-foreground">
                          <Star className="h-3 w-3 fill-warning text-warning" aria-hidden />
                          {asset.averageRating.toFixed(1)}
                          {asset.reviewCount ? ` (${asset.reviewCount})` : null}
                        </span>
                      ) : null}
                    </div>
                    <Button size="sm" variant="ghost" asChild onClick={() => void mutate()}>
                      <Link href={`/marketplace/assets/${encodeURIComponent(asset.slug)}`}>
                        Open
                        <ChevronRight className="ml-1 h-3.5 w-3.5" aria-hidden />
                      </Link>
                    </Button>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </AppShell>
  )
}
