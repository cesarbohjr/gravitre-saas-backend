"use client"

import { Suspense, useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { Check, ChevronDown, LayoutGrid, List, Loader2, Search } from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitreEmpty } from "@/components/gravitre/nodus-product"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Skeleton } from "@/components/ui/skeleton"
import { toast } from "@/components/agents/overlays/toast"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { InstallStepperSheet } from "@/components/marketplace/install-experience"
import { isFreeAsset } from "@/components/marketplace/marketplace-asset-commerce"
import {
  FeaturedListingCard,
  ListingCard,
  ListingRow,
  type ListingActionHandlers,
} from "@/components/marketplace/catalog/listing-card"
import "@/components/marketplace/catalog/catalog.css"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { identityDepartmentFor } from "@/lib/listing-identity"
import {
  READINESS_FILTERS,
  listingReadiness,
  matchesReadiness,
  type ListingReadiness,
  type ReadinessFilter,
} from "@/lib/listing-readiness"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { cn } from "@/lib/utils"
import type { MarketplaceAssetSummary, MarketplaceFacetCount } from "@/types/api"

/** Listing type tabs. The first six always show; the rest appear once the catalog has any. */
const TYPE_FILTERS = [
  { id: "all", label: "All" },
  { id: "ai_agent", label: "Agents" },
  { id: "workflow", label: "Workflows" },
  { id: "knowledge_pack", label: "Knowledge" },
  { id: "department_pack", label: "Packs" },
  { id: "connector_config", label: "Connectors" },
  { id: "play", label: "Plays" },
  { id: "outcome_pack", label: "Outcome packs" },
  { id: "dataset_pack", label: "Datasets" },
  { id: "dashboard_pack", label: "Dashboards" },
  { id: "capability_package", label: "Skills & plugins" },
] as const

const PRIMARY_TYPES = new Set(["all", "ai_agent", "workflow", "knowledge_pack", "department_pack", "connector_config"])

const PRICE_FILTERS = [
  { id: "all", label: "Any price" },
  { id: "free", label: "Free" },
  { id: "paid", label: "Paid" },
] as const
type PriceFilter = (typeof PRICE_FILTERS)[number]["id"]

const SORTS = [
  { id: "recommended", label: "Recommended" },
  { id: "newest", label: "Newest" },
  { id: "installs", label: "Most installed" },
] as const
type SortId = (typeof SORTS)[number]["id"]

const PAGE_SIZES = [24, 48, 96] as const

/** The API pages at 100; the catalog is small enough to load whole so readiness can be filtered. */
const CATALOG_CAP = 500

async function loadCatalog(params: { assetType?: string; department?: string; search?: string; sort: SortId }) {
  const first = await marketplaceApi.listAssets({ ...params, limit: 100, offset: 0 })
  const assets = [...first.assets]
  while (assets.length < first.total && assets.length < CATALOG_CAP) {
    const next = await marketplaceApi.listAssets({ ...params, limit: 100, offset: assets.length })
    if (next.assets.length === 0) break
    assets.push(...next.assets)
  }
  return { assets, total: first.total }
}

/** Merges facet counts whose labels are equivalent once normalized, so "Operations" never appears twice. */
function dedupeFacets(items: MarketplaceFacetCount[]): MarketplaceFacetCount[] {
  const merged = new Map<string, MarketplaceFacetCount>()
  for (const item of items) {
    const norm = item.key.trim().toLowerCase().replace(/[\s_-]+/g, " ")
    const existing = merged.get(norm)
    if (existing) existing.count += item.count
    else merged.set(norm, { ...item })
  }
  return Array.from(merged.values())
}

function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}

type FeaturedPick = { asset: MarketplaceAssetSummary; reason: string; fromApps: boolean }

/**
 * Up to three picks: listings that use an app this workspace already connected
 * first, then listings Gravitre marks as featured. Nothing is invented: with
 * neither, the row does not show.
 */
function pickFeatured(assets: MarketplaceAssetSummary[]): FeaturedPick[] {
  const picks: FeaturedPick[] = []
  const seen = new Set<string>()
  const ranked = [...assets].sort((a, b) => Number(Boolean(b.featured)) - Number(Boolean(a.featured)))
  for (const asset of ranked) {
    if (picks.length >= 3) break
    const app = asset.connectorChecklist?.find((item) => item.connected)
    if (!app || seen.has(asset.id)) continue
    seen.add(asset.id)
    picks.push({ asset, reason: `Uses your ${app.label || app.connectorType}`, fromApps: true })
  }
  for (const asset of ranked) {
    if (picks.length >= 3) break
    if (!asset.featured || asset.installed || seen.has(asset.id)) continue
    seen.add(asset.id)
    const dept = asset.department ? identityDepartmentFor(asset.department).label : null
    picks.push({ asset, reason: dept ? `Built for ${dept}` : "Featured", fromApps: false })
  }
  return picks
}

function CardSkeleton() {
  return (
    <div className="mp-card">
      <Skeleton className="h-[136px] w-full rounded-none" />
      <div className="flex flex-col gap-3 p-4">
        <div className="flex items-center gap-3">
          <Skeleton className="size-11 rounded-full" />
          <Skeleton className="h-4 w-40" />
        </div>
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-2/3" />
      </div>
      <Skeleton className="h-14 w-full rounded-none" />
    </div>
  )
}

function FilterMenu<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: T
  options: ReadonlyArray<{ id: T; label: string; count?: number }>
  onChange: (next: T) => void
}) {
  const active = options.find((option) => option.id === value)
  const isFiltered = value !== options[0]?.id
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" className="mp-filter" data-active={isFiltered}>
          {isFiltered && active ? active.label : label}
          <ChevronDown size={14} strokeWidth={2.2} aria-hidden />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-60">
        {options.map((option) => (
          <DropdownMenuItem key={option.id} className="min-h-11 md:min-h-9" onSelect={() => onChange(option.id)}>
            <span className="flex-1">{option.label}</span>
            {option.count != null ? <span className="text-xs tabular-nums text-muted-foreground">{option.count}</span> : null}
            {option.id === value ? <Check className="size-4" aria-hidden /> : null}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function pageWindow(current: number, total: number): number[] {
  const start = Math.max(1, Math.min(current - 2, total - 4))
  return Array.from({ length: Math.min(5, total) }, (_, index) => start + index)
}

function MarketplaceAssetsContent() {
  const { user } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const initialSlug = searchParams.get("slug")
  const initialType = searchParams.get("type")
  const initialPrice = searchParams.get("price")
  const initialReadiness = searchParams.get("readiness")
  const initialSort = searchParams.get("sort")
  const { isAdmin, loading: roleLoading } = useOrgAdmin()

  const [typeFilter, setTypeFilter] = useState<string>(
    initialType && TYPE_FILTERS.some((filter) => filter.id === initialType) ? initialType : "all",
  )
  const [departmentFilter, setDepartmentFilter] = useState<string | null>(searchParams.get("department"))
  const [priceFilter, setPriceFilter] = useState<PriceFilter>(
    initialPrice === "free" || initialPrice === "paid" ? initialPrice : "all",
  )
  const [readinessFilter, setReadinessFilter] = useState<ReadinessFilter>(
    READINESS_FILTERS.some((filter) => filter.id === initialReadiness) ? (initialReadiness as ReadinessFilter) : "all",
  )
  const [sort, setSort] = useState<SortId>(SORTS.some((option) => option.id === initialSort) ? (initialSort as SortId) : "recommended")
  const [view, setView] = useState<"grid" | "list">(searchParams.get("view") === "list" ? "list" : "grid")
  const [pageSize, setPageSize] = useState<number>(24)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState(searchParams.get("search") ?? "")
  const debouncedSearch = useDebouncedValue(search.trim())
  const [installTarget, setInstallTarget] = useState<MarketplaceAssetSummary | null>(null)
  const [installOpen, setInstallOpen] = useState(false)

  usePublishGravitreAISelection(
    installTarget ? { kind: "marketplace_asset", id: installTarget.id, label: installTarget.title } : null,
  )

  useEffect(() => {
    if (initialSlug) router.replace(`/marketplace/assets/${encodeURIComponent(initialSlug)}`)
  }, [initialSlug, router])

  // Any filter change starts again from the first page.
  useEffect(() => {
    setPage(1)
  }, [typeFilter, departmentFilter, priceFilter, readinessFilter, sort, debouncedSearch, pageSize])

  const syncFiltersToUrl = useCallback(() => {
    const params = new URLSearchParams()
    if (typeFilter !== "all") params.set("type", typeFilter)
    if (departmentFilter) params.set("department", departmentFilter)
    if (priceFilter !== "all") params.set("price", priceFilter)
    if (readinessFilter !== "all") params.set("readiness", readinessFilter)
    if (sort !== "recommended") params.set("sort", sort)
    if (view !== "grid") params.set("view", view)
    if (debouncedSearch) params.set("search", debouncedSearch)
    const next = params.toString()
    if (next === searchParams.toString()) return
    router.replace(next ? `/marketplace/assets?${next}` : "/marketplace/assets", { scroll: false })
  }, [debouncedSearch, departmentFilter, priceFilter, readinessFilter, router, searchParams, sort, typeFilter, view])

  useEffect(() => {
    syncFiltersToUrl()
  }, [syncFiltersToUrl])

  useEffect(() => {
    if (!roleLoading && !isAdmin && typeFilter === "capability_package") setTypeFilter("all")
  }, [isAdmin, roleLoading, typeFilter])

  const { data, error, isLoading, mutate } = useSWR(
    user ? (["marketplace-catalog", typeFilter, departmentFilter, debouncedSearch, sort] as const) : null,
    () =>
      loadCatalog({
        assetType: typeFilter === "all" ? undefined : typeFilter,
        department: departmentFilter ?? undefined,
        search: debouncedSearch || undefined,
        sort,
      }),
  )

  const includeFederated = (typeFilter === "all" || typeFilter === "connector_config") && !departmentFilter
  const {
    data: federatedData,
    error: federatedError,
    mutate: refreshFederated,
  } = useSWR(user && includeFederated ? (["marketplace-federated-connectors", debouncedSearch] as const) : null, () =>
    marketplaceApi.listFederatedConnectors({ search: debouncedSearch || undefined, limit: 100 }),
  )

  const {
    data: categories,
    error: categoryError,
    mutate: refreshCategories,
  } = useSWR(user ? "marketplace-categories" : null, () => marketplaceApi.listCategories())

  const departmentFacets = useMemo(() => dedupeFacets(categories?.departments ?? []), [categories?.departments])

  const typeCounts = useMemo(() => {
    const map = new Map<string, number>()
    for (const item of categories?.assetTypes ?? []) map.set(item.key.trim().toLowerCase(), item.count)
    return map
  }, [categories?.assetTypes])

  const typeOptions = useMemo(
    () =>
      TYPE_FILTERS.map((filter) => ({
        id: filter.id as string,
        label: filter.label as string,
        count: filter.id === "all" ? categories?.totalAssets : typeCounts.get(filter.id),
        primary: PRIMARY_TYPES.has(filter.id),
      })).filter(
        (option) =>
          (isAdmin || option.id !== "capability_package") &&
          (option.primary || Boolean(option.count) || typeFilter === option.id),
      ),
    [categories?.totalAssets, isAdmin, typeCounts, typeFilter],
  )

  const departmentOptions = useMemo(
    () => [
      { id: "", label: "All departments" },
      ...departmentFacets.map((facet) => ({ id: facet.key, label: identityDepartmentFor(facet.key).label, count: facet.count })),
    ],
    [departmentFacets],
  )

  const assets = useMemo(() => {
    const catalog = data?.assets ?? []
    if (!includeFederated || !federatedData?.assets?.length) return catalog
    const linkedRegistryIds = new Set(catalog.map((asset) => asset.partnerRegistryId).filter((id): id is string => Boolean(id)))
    const federatedExtras = federatedData.assets
      .filter((asset) => !linkedRegistryIds.has(asset.registryId ?? asset.id))
      .map(
        (asset): MarketplaceAssetSummary => ({
          ...asset,
          tags: asset.tags ?? [],
          canInstall: asset.canInstall ?? false,
          installed: asset.installed ?? false,
          federated: true,
          source: asset.source ?? "partner_registry",
        }),
      )
    return [...catalog, ...federatedExtras]
  }, [data?.assets, federatedData?.assets, includeFederated])

  const readinessById = useMemo(() => {
    const map = new Map<string, ListingReadiness>()
    for (const asset of assets) map.set(asset.id, listingReadiness(asset, { canInstall: isAdmin }))
    return map
  }, [assets, isAdmin])

  useEffect(() => {
    const purchase = searchParams.get("purchase")
    const purchaseSlug = searchParams.get("slug")
    if (purchase !== "success" || !purchaseSlug || !assets.length) return
    const asset = assets.find((row) => row.slug === purchaseSlug)
    if (asset) {
      toast.info("Checkout returned", {
        eyebrow: "Marketplace",
        description: "Installation will check your workspace entitlement before proceeding.",
      })
      setInstallTarget(asset)
      setInstallOpen(true)
    }
    const params = new URLSearchParams(searchParams.toString())
    params.delete("purchase")
    params.delete("slug")
    const next = params.toString()
    router.replace(next ? `/marketplace/assets?${next}` : "/marketplace/assets", { scroll: false })
  }, [assets, router, searchParams])

  const visibleAssets = useMemo(
    () =>
      assets.filter((asset) => {
        if (priceFilter === "free" && !isFreeAsset(asset)) return false
        if (priceFilter === "paid" && isFreeAsset(asset)) return false
        const readiness = readinessById.get(asset.id)
        return readiness ? matchesReadiness(readiness, readinessFilter) : true
      }),
    [assets, priceFilter, readinessById, readinessFilter],
  )

  const pageCount = Math.max(1, Math.ceil(visibleAssets.length / pageSize))
  const currentPage = Math.min(page, pageCount)
  const pageAssets = visibleAssets.slice((currentPage - 1) * pageSize, currentPage * pageSize)

  const hasFilters =
    typeFilter !== "all" || Boolean(departmentFilter) || priceFilter !== "all" || readinessFilter !== "all" || Boolean(debouncedSearch)
  const featured = useMemo(() => (hasFilters ? [] : pickFeatured(assets)), [assets, hasFilters])
  const catalogTotal = categories?.totalAssets ?? data?.total

  const handlers: ListingActionHandlers = useMemo(
    () => ({
      onOpenDetail: (asset) => router.push(`/marketplace/assets/${encodeURIComponent(asset.slug)}`),
      onInstall: (asset) => {
        setInstallTarget(asset)
        setInstallOpen(true)
      },
      onOpenInstalled: (asset) =>
        router.push(asset.assetType === "connector_config" ? "/connectors" : "/marketplace/installed"),
    }),
    [router],
  )

  const emptyMessage = useMemo(() => {
    if (readinessFilter !== "all") return "No listings match this readiness."
    if (priceFilter === "free") return "No free listings match the current filters."
    if (priceFilter === "paid") return "No paid listings match the current filters."
    if (debouncedSearch) return "No listings match your search."
    if (departmentFilter) return `No listings for ${identityDepartmentFor(departmentFilter).label} yet.`
    if (typeFilter !== "all") return "No listings of this type yet."
    if (categories?.totalAssets === 0) return "The catalog is empty right now. Check back soon for new listings."
    return "No listings found."
  }, [readinessFilter, priceFilter, debouncedSearch, departmentFilter, typeFilter, categories?.totalAssets])

  const clearFilters = () => {
    setTypeFilter("all")
    setDepartmentFilter(null)
    setPriceFilter("all")
    setReadinessFilter("all")
    setSearch("")
  }

  return (
    <AppShell title="Marketplace">
      {/* shrink-0 keeps AppShell's flex-col <main> from compressing the catalog. */}
      <div
        className="mp relative shrink-0 bg-[color:var(--g-canvas)] px-[var(--np-page-pad-sm)] pb-16 pt-6 sm:px-[var(--np-page-pad)] sm:pt-8"
        data-testid="marketplace-catalog-b"
        data-composition="discover"
      >
        <div className="mx-auto flex max-w-[1240px] flex-col gap-6">
          <header className="mp-head">
            <h1 className="mp-title">Marketplace</h1>
            <div role="tablist" aria-label="Listing type" className="mp-tabs">
              {typeOptions.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  role="tab"
                  aria-selected={typeFilter === option.id}
                  className="mp-tab"
                  onClick={() => setTypeFilter(option.id)}
                >
                  {option.label}
                  {option.count != null ? <span className="mp-count">{option.count}</span> : null}
                </button>
              ))}
            </div>
            <div className="mp-head-tools">
              <label className="mp-search">
                <Search size={16} aria-hidden />
                <input
                  type="search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder={catalogTotal ? `Search ${catalogTotal} listings` : "Search the catalog"}
                  aria-label="Search the catalog"
                />
              </label>
              <div role="group" aria-label="View" className="mp-view">
                <button type="button" aria-label="Grid view" aria-pressed={view === "grid"} onClick={() => setView("grid")}>
                  <LayoutGrid size={18} aria-hidden />
                </button>
                <button type="button" aria-label="List view" aria-pressed={view === "list"} onClick={() => setView("list")}>
                  <List size={18} aria-hidden />
                </button>
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button type="button" className="mp-filter">
                    Manage
                    <ChevronDown size={14} strokeWidth={2.2} aria-hidden />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-60">
                  <DropdownMenuLabel className="text-xs font-medium text-muted-foreground">Your workspace</DropdownMenuLabel>
                  {[
                    { href: "/marketplace/installed", label: "Installed listings" },
                    { href: "/marketplace/saved", label: "Saved for later" },
                    ...(isAdmin ? [{ href: "/marketplace/capabilities", label: "Skills & plugins" }] : []),
                  ].map((link) => (
                    <DropdownMenuItem key={link.href} asChild className="min-h-11 md:min-h-9">
                      <Link href={link.href}>{link.label}</Link>
                    </DropdownMenuItem>
                  ))}
                  <DropdownMenuSeparator />
                  <DropdownMenuLabel className="text-xs font-medium text-muted-foreground">Partners</DropdownMenuLabel>
                  {[
                    { href: "/marketplace/connectors", label: "Partner connectors" },
                    { href: "/marketplace/submit", label: "Submit a listing" },
                    { href: "/connectors", label: "Connected apps" },
                  ].map((link) => (
                    <DropdownMenuItem key={link.href} asChild className="min-h-11 md:min-h-9">
                      <Link href={link.href}>{link.label}</Link>
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </header>

          {featured.length > 0 ? (
            <section aria-labelledby="marketplace-featured-heading" className="flex flex-col gap-4">
              <div className="mp-section-head">
                <h2 id="marketplace-featured-heading">Featured for your workspace</h2>
                <span>
                  {featured.some((pick) => pick.fromApps) ? "Picked from your connected apps" : "Picked by Gravitre"}
                  <AskGravitreSummonButton
                    className="ml-3"
                    label="Ask for a pick"
                    prompt="Help me find a Marketplace listing that fits my connected apps and inspect its required systems, permissions and readiness."
                  />
                </span>
              </div>
              <div className="mp-featured">
                {featured.map((pick) => (
                  <FeaturedListingCard
                    key={pick.asset.id}
                    asset={pick.asset}
                    reason={pick.reason}
                    readiness={readinessById.get(pick.asset.id) ?? listingReadiness(pick.asset, { canInstall: isAdmin })}
                    handlers={handlers}
                  />
                ))}
              </div>
            </section>
          ) : null}

          <section
            aria-labelledby="marketplace-discovery-heading"
            data-review-surface="marketplace-discovery"
            className="flex flex-col gap-4"
          >
            <h2 id="marketplace-discovery-heading" className="sr-only">
              Catalog
            </h2>
            <div role="toolbar" aria-label="Filters" className="flex flex-wrap items-center gap-2">
              <FilterMenu
                label="Department"
                value={departmentFilter ?? ""}
                options={departmentOptions}
                onChange={(next) => setDepartmentFilter(next || null)}
              />
              <FilterMenu label="Readiness" value={readinessFilter} options={READINESS_FILTERS} onChange={setReadinessFilter} />
              <FilterMenu label="Price" value={priceFilter} options={PRICE_FILTERS} onChange={setPriceFilter} />
              {hasFilters ? (
                <button type="button" className="mp-btn ghost" onClick={clearFilters}>
                  Clear
                </button>
              ) : null}
              <span className="flex-[1_1_20px]" />
              <span className="text-sm text-[color:var(--mp-muted)]">
                <strong className="font-semibold text-[color:var(--mp-ink)]">{pageAssets.length}</strong> of {visibleAssets.length}{" "}
                {visibleAssets.length === 1 ? "listing" : "listings"}
              </span>
              <label className="flex items-center gap-2 text-sm text-[color:var(--mp-muted)]">
                Sort
                <select className="mp-select" value={sort} onChange={(event) => setSort(event.target.value as SortId)}>
                  {SORTS.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {error || federatedError || categoryError ? (
              <div role="alert" className="flex flex-col items-start gap-2 border-l-2 border-[color:var(--g-warmth)] pl-4 text-sm">
                <p>Some catalog data could not be refreshed. Loaded listings remain available.</p>
                <button
                  type="button"
                  className="mp-btn ghost"
                  onClick={() => void Promise.allSettled([mutate(), refreshFederated(), refreshCategories()])}
                >
                  Retry catalog
                </button>
              </div>
            ) : null}

            {isLoading && !data ? (
              <div className="mp-grid">
                {Array.from({ length: 8 }).map((_, index) => (
                  <CardSkeleton key={index} />
                ))}
              </div>
            ) : !data && !federatedData ? null : visibleAssets.length === 0 ? (
              <GravitreEmpty
                illustration="moment-focus-time"
                title={emptyMessage}
                hint="Adjust filters or clear search to see more listings."
              />
            ) : view === "grid" ? (
              <div className={cn("mp-grid li-still")} data-testid="marketplace-scan-list">
                {pageAssets.map((asset) => (
                  <ListingCard
                    key={asset.id}
                    asset={asset}
                    readiness={readinessById.get(asset.id)!}
                    handlers={handlers}
                    busy={installOpen && installTarget?.id === asset.id}
                  />
                ))}
              </div>
            ) : (
              <ul className="mp-list" data-testid="marketplace-scan-list">
                {pageAssets.map((asset) => (
                  <ListingRow
                    key={asset.id}
                    asset={asset}
                    readiness={readinessById.get(asset.id)!}
                    handlers={handlers}
                    busy={installOpen && installTarget?.id === asset.id}
                  />
                ))}
              </ul>
            )}

            {visibleAssets.length > PAGE_SIZES[0] ? (
              <div className="mp-pages">
                <label className="flex items-center gap-2 text-sm text-[color:var(--mp-muted)]">
                  Per page
                  <select className="mp-select" value={pageSize} onChange={(event) => setPageSize(Number(event.target.value))}>
                    {PAGE_SIZES.map((size) => (
                      <option key={size} value={size}>
                        {size}
                      </option>
                    ))}
                  </select>
                </label>
                {pageCount > 1 ? (
                  <nav aria-label="Pages">
                    {pageWindow(currentPage, pageCount).map((number) => (
                      <button
                        key={number}
                        type="button"
                        className="mp-page"
                        aria-current={number === currentPage ? "page" : undefined}
                        onClick={() => setPage(number)}
                      >
                        {number}
                      </button>
                    ))}
                    <button
                      type="button"
                      className="mp-page"
                      disabled={currentPage >= pageCount}
                      onClick={() => setPage(currentPage + 1)}
                    >
                      Next
                    </button>
                  </nav>
                ) : null}
              </div>
            ) : null}
          </section>
        </div>
      </div>

      <InstallStepperSheet
        asset={installTarget}
        open={installOpen}
        onOpenChange={setInstallOpen}
        onComplete={() => void mutate()}
        isAdmin={isAdmin}
      />
    </AppShell>
  )
}

export default function MarketplaceAssetsPage() {
  return (
    <Suspense
      fallback={
        <div className="grid min-h-[40vh] place-items-center text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
        </div>
      }
    >
      <MarketplaceAssetsContent />
    </Suspense>
  )
}
