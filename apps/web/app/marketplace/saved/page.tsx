"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import { motion, useReducedMotion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitreEmpty,
  GravitreMetric,
  GravitrePageHeader,
  GravitreSurface,
} from "@/components/gravitre/nodus-product"
import { CategoryIconChip } from "@/components/marketplace/category-icon-chip"
import type { AssetCategory } from "@/lib/marketplace-category-icons"
import { AssetSaveButton } from "@/components/marketplace/asset-save-button"
import { ErrorState } from "@/components/gravitre/empty-state"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { ArrowLeft, Bookmark, ChevronRight, Star } from "lucide-react"

export default function MarketplaceSavedPage() {
  const { user } = useAuth()
  const router = useRouter()
  const reduced = useReducedMotion()
  const { data, error, isLoading, mutate } = useSWR(user ? "marketplace-saves-page" : null, () =>
    marketplaceApi.listSaves({ limit: 100 }),
  )

  const saves = data?.saves ?? []

  return (
    <AppShell title="Saved assets">
      <div className="bg-[color:var(--g-canvas)]">
        <GravitrePageHeader
          eyebrow="Gravitre Marketplace"
          title="Saved assets"
          description="Assets you bookmarked from the unified marketplace catalog."
          icon={<Bookmark className="h-5 w-5" />}
          actions={
            <Button variant="outline" size="sm" asChild>
              <Link href="/marketplace/assets">
                <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
                Catalog
              </Link>
            </Button>
          }
        />

        <div className="mx-auto max-w-4xl space-y-6 px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)] sm:py-5">
          <section className="grid grid-cols-2 gap-[var(--np-kpi-gap)] sm:grid-cols-3">
            <GravitreMetric
              label="Saved"
              value={isLoading ? "—" : saves.length}
              hint="Bookmarks"
              icon={<Bookmark className="h-4 w-4" />}
            />
          </section>

          {isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-36 rounded-[var(--np-radius-lg)]" />
              ))}
            </div>
          ) : error ? (
            <ErrorState
              title="Could not load saved assets"
              description="Something went wrong fetching your bookmarks. Please try again."
              onRetry={() => void mutate()}
            />
          ) : saves.length === 0 ? (
            <GravitreEmpty
              icon={<Bookmark className="h-5 w-5" />}
              title="No saved assets yet"
              hint="Bookmark assets from the marketplace catalog and they'll show up here for quick access."
              action={
                <Button onClick={() => router.push("/marketplace/assets")}>Browse catalog</Button>
              }
            />
          ) : (
            <ul className="grid gap-4 sm:grid-cols-2">
              {saves.map((entry, index) => {
                const asset = entry.asset
                if (!asset) return null
                return (
                  <motion.li
                    key={entry.id}
                    initial={reduced ? false : { opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: reduced ? 0 : Math.min(index, 8) * 0.05 }}
                  >
                    <GravitreSurface className="flex h-full flex-col transition-[transform,box-shadow] duration-200 ease-out hover:-translate-y-1 hover:shadow-md">
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
                            <h2 className="truncate font-semibold leading-tight">{asset.title}</h2>
                            <p className="truncate text-xs text-muted-foreground">
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
                    </GravitreSurface>
                  </motion.li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </AppShell>
  )
}
