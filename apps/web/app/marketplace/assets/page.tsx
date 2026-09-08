"use client"

import { Suspense, useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { motion, useReducedMotion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitreEmpty,
  GravitreMetric,
  GravitrePageHeader,
  GravitreSurface,
} from "@/components/gravitre/nodus-product"
import { AssetTrustBadges } from "@/components/marketplace/asset-trust-badges"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { FilterChip, SegmentedControl } from "@/components/gravitre/filter-chip"
import { TYPE } from "@/lib/design-system"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { cn } from "@/lib/utils"
import {
  Bot,
  CheckCircle2,
  ChevronRight,
  Copy,
  Database,
  Loader2,
  Package,
  Plug,
  Search,
  ShoppingCart,
  Sparkles,
  Star,
  Workflow,
} from "lucide-react"
import { toast } from "sonner"
import type {
  MarketplaceAssetSummary,
  MarketplaceFacetCount,
} from "@/types/api"
import { CategoryIconChip } from "@/components/marketplace/category-icon-chip"
import { AssetSaveButton } from "@/components/marketplace/asset-save-button"
import {
  EntitlementBadge,
  NonAdminPurchaseNotice,
  PackContentsPreview,
  PriceBadge,
  assetRequiresPurchase,
  formatAssetPrice,
  isFreeAsset,
} from "@/components/marketplace/marketplace-asset-commerce"
import { InstallStepperSheet } from "@/components/marketplace/install-experience"
import type { AssetCategory } from "@/lib/marketplace-category-icons"

const TYPE_FILTERS = [
  { id: "all", label: "All" },
  { id: "ai_agent", label: "Agents", icon: Bot },
  { id: "workflow", label: "Workflows", icon: Workflow },
  { id: "knowledge_pack", label: "Knowledge", icon: Database },
  { id: "department_pack", label: "Department packs", icon: Package },
  { id: "connector_config", label: "Partner connectors", icon: Plug },
] as const

const PRICE_FILTERS = [
  { id: "all", label: "All prices" },
  { id: "free", label: "Free" },
  { id: "paid", label: "Paid" },
] as const

type PriceFilter = (typeof PRICE_FILTERS)[number]["id"]

/** Single-line summary of an asset's connector setup, shown on catalog cards. */
function connectorSummary(asset: MarketplaceAssetSummary): string {
  const total = asset.connectorChecklist?.length ?? 0
  if (total === 0) return "No setup required"
  const required = asset.requiredConnectorsTotal ?? 0
  const optional = total - required
  const parts: string[] = []
  if (required > 0) parts.push(`${required} required`)
  if (optional > 0) parts.push(`${optional} optional`)
  const detail = parts.length ? ` · ${parts.join(", ")}` : ""
  return `${total} app${total === 1 ? "" : "s"} to connect${detail}`
}

/**
 * Merges facet counts whose labels are equivalent once normalized (casing,
 * spacing, separators), so e.g. "Operations" never appears twice in the rail.
 */
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

function ReadinessRing({
  connected,
  total,
  ready,
}: {
  connected: number
  total: number
  ready: boolean
}) {
  if (total === 0) {
    return (
      <span className="grid h-9 w-9 place-items-center rounded-full bg-success/15 text-success" title="No connectors required">
        <CheckCircle2 className="h-4 w-4" aria-hidden />
      </span>
    )
  }
  const pct = Math.min(100, Math.round((connected / total) * 100))
  const ringClass = ready ? "text-success" : connected > 0 ? "text-warning" : "text-destructive"
  return (
    <div className={cn("relative h-9 w-9", ringClass)} title={`${connected}/${total} required connectors ready`}>
      <svg className="h-9 w-9 -rotate-90 text-muted/30" viewBox="0 0 36 36" aria-hidden>
        <circle cx="18" cy="18" r="15" fill="none" stroke="currentColor" strokeWidth="3" className="opacity-30" />
        <circle
          cx="18"
          cy="18"
          r="15"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          strokeDasharray={`${pct} 100`}
          strokeLinecap="round"
        />
      </svg>
      <span className="absolute inset-0 grid place-items-center text-[10px] font-semibold tabular-nums">
        {connected}/{total}
      </span>
    </div>
  )
}

function AssetCardSkeleton() {
  return (
    <div className="flex h-full flex-col rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-5 shadow-[var(--np-shadow)]">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <Skeleton className="h-10 w-10 rounded-[var(--np-radius-md)]" />
          <div className="space-y-2">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-20" />
          </div>
        </div>
        <Skeleton className="h-9 w-9 rounded-full" />
      </div>
      <Skeleton className="mb-4 h-12 w-full" />
      <Skeleton className="mb-4 h-16 w-full rounded-[var(--np-radius-md)]" />
      <div className="mt-auto flex gap-2">
        <Skeleton className="h-8 w-20" />
        <Skeleton className="h-8 w-20" />
      </div>
    </div>
  )
}

function AssetCard({
  asset,
  index,
  isAdmin,
  busy,
  reduceMotion,
  onOpenDetail,
  onInstall,
  onClone,
}: {
  asset: MarketplaceAssetSummary
  index: number
  isAdmin: boolean
  busy: string | null
  reduceMotion: boolean | null
  onOpenDetail: (asset: MarketplaceAssetSummary) => void
  onInstall: (asset: MarketplaceAssetSummary) => void
  onClone: (asset: MarketplaceAssetSummary) => void
}) {
  const ready = asset.connectorsReady || asset.requiredConnectorsTotal === 0
  const blocked = !ready && !asset.installed
  const needsPurchase = assetRequiresPurchase(asset)
  const showPrimaryAction = isAdmin && !asset.installed

  return (
    <motion.article
      layout={!reduceMotion}
      initial={reduceMotion ? false : { opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={reduceMotion ? undefined : { y: -3 }}
      transition={{ duration: 0.35, delay: reduceMotion ? 0 : index * 0.04 }}
      className={cn(
        "group relative flex h-full flex-col overflow-hidden border border-divide bg-[color:var(--g-surface-1)] p-5 shadow-[var(--np-shadow)] transition-shadow hover:shadow-md",
        "rounded-[var(--np-radius-lg)]",
        asset.installed ? "border-success/30" : "hover:border-[color:var(--g-brand-border)]",
      )}
    >
      <div className="relative mb-3 flex items-start justify-between gap-3">
        <button
          type="button"
          onClick={() => onOpenDetail(asset)}
          className="flex min-w-0 flex-1 items-center gap-3 text-left"
        >
          <CategoryIconChip
            assetType={asset.assetType as AssetCategory}
            department={asset.department}
            size="md"
          />
          <div className="min-w-0">
            <h3 className={TYPE.cardTitle}>{asset.title}</h3>
            <p className="text-xs capitalize text-muted-foreground">
              {(asset.department ?? asset.assetType).replace(/_/g, " ")}
            </p>
          </div>
        </button>
        <div className="flex shrink-0 items-center gap-1">
          <AssetSaveButton slug={asset.slug} assetId={asset.id} size="icon" variant="outline" />
          <ReadinessRing
            connected={asset.requiredConnectorsConnected ?? 0}
            total={asset.requiredConnectorsTotal ?? 0}
            ready={ready}
          />
        </div>
      </div>

      <div className="mb-2 flex flex-wrap items-center gap-2">
        <PriceBadge asset={asset} />
        <EntitlementBadge asset={asset} />
        {asset.federated || asset.source === "partner_registry" ? (
          <Badge variant="outline">Partner registry</Badge>
        ) : null}
        {asset.visibility === "internal" ? (
          <Badge variant="outline">Internal</Badge>
        ) : null}
        <AssetTrustBadges asset={asset} />
        {asset.installCount != null && asset.installCount > 0 ? (
          <span className="text-[11px] text-muted-foreground">{asset.installCount.toLocaleString()} installs</span>
        ) : null}
        {asset.averageRating != null ? (
          <span className="inline-flex items-center gap-0.5 text-[11px] text-muted-foreground">
            <Star className="h-3 w-3 fill-warning text-warning" aria-hidden />
            {asset.averageRating.toFixed(1)}
            {asset.reviewCount ? (
              <span className="text-muted-foreground/80"> · {asset.reviewCount} reviews</span>
            ) : null}
          </span>
        ) : null}
      </div>

      {asset.description ? (
        <p className="mb-4 line-clamp-3 flex-1 text-sm text-muted-foreground">{asset.description}</p>
      ) : (
        <div className="flex-1" />
      )}

      <div className="mb-4 flex flex-wrap gap-1.5">
        {(asset.tags ?? []).slice(0, 4).map((tag) => (
          <Badge key={tag} variant="outline" className="text-[10px]">
            {tag}
          </Badge>
        ))}
      </div>

      <PackContentsPreview items={asset.packItems} compact />

      <div className="mb-4 flex items-center gap-1.5 text-xs text-muted-foreground">
        <Plug className="h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className="truncate">{connectorSummary(asset)}</span>
      </div>

      {!isAdmin && needsPurchase ? <div className="mb-4"><NonAdminPurchaseNotice /></div> : null}

      <div className="mt-auto flex flex-col gap-2">
        {showPrimaryAction ? (
          <Button
            size="sm"
            className={cn(
              "h-10 w-full rounded-full font-semibold shadow-sm",
              !blocked && !needsPurchase && "bg-foreground text-background hover:bg-foreground/90",
            )}
            disabled={Boolean(busy)}
            onClick={() => onInstall(asset)}
            title={blocked && !needsPurchase ? "Connect required apps first" : undefined}
          >
            {busy === asset.id ? (
              <>
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
                Installing…
              </>
            ) : needsPurchase ? (
              <>
                <ShoppingCart className="mr-1.5 h-3.5 w-3.5" aria-hidden />
                {`Buy & install · ${formatAssetPrice(asset)}`}
              </>
            ) : blocked ? (
              "Connect apps to install"
            ) : (
              <>
                <Sparkles className="mr-1.5 h-3.5 w-3.5" aria-hidden />
                Install to workspace
              </>
            )}
          </Button>
        ) : asset.installed ? (
          <Button size="sm" className="h-10 w-full rounded-full font-semibold" asChild>
            <Link href="/marketplace/installed">
              <CheckCircle2 className="mr-1.5 h-3.5 w-3.5 text-success" aria-hidden />
              Open installed
            </Link>
          </Button>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            className="flex-1 rounded-full"
            onClick={() => onOpenDetail(asset)}
          >
            Details
            <ChevronRight className="ml-1 h-3.5 w-3.5" aria-hidden />
          </Button>
          {isAdmin ? (
            <Button size="sm" variant="ghost" className="rounded-full" disabled={Boolean(busy)} onClick={() => onClone(asset)}>
              {busy === `clone:${asset.id}` ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
              ) : (
                <Copy className="mr-1.5 h-3.5 w-3.5" aria-hidden />
              )}
              Clone
            </Button>
          ) : null}
        </div>
      </div>
    </motion.article>
  )
}

function MarketplaceAssetsContent() {
  const { user } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const initialSlug = searchParams.get("slug")
  const initialType = searchParams.get("type")
  const initialDepartment = searchParams.get("department")
  const initialPrice = searchParams.get("price")
  const reduceMotion = useReducedMotion()
  const { isAdmin } = useOrgAdmin()
  const validTypes = useMemo(() => new Set(TYPE_FILTERS.map((filter) => filter.id)), [])
  const [typeFilter, setTypeFilter] = useState<string>(
    initialType && validTypes.has(initialType as (typeof TYPE_FILTERS)[number]["id"]) ? initialType : "all",
  )
  const [departmentFilter, setDepartmentFilter] = useState<string | null>(initialDepartment)
  const [priceFilter, setPriceFilter] = useState<PriceFilter>(
    initialPrice === "free" || initialPrice === "paid" ? initialPrice : "all",
  )
  const [search, setSearch] = useState("")
  const debouncedSearch = useDebouncedValue(search.trim())
  const [busy, setBusy] = useState<string | null>(null)
  const [installTarget, setInstallTarget] = useState<MarketplaceAssetSummary | null>(null)
  const [installOpen, setInstallOpen] = useState(false)

  useEffect(() => {
    if (initialSlug) {
      router.replace(`/marketplace/assets/${encodeURIComponent(initialSlug)}`)
    }
  }, [initialSlug, router])

  const syncFiltersToUrl = useCallback(() => {
    const params = new URLSearchParams()
    if (typeFilter !== "all") params.set("type", typeFilter)
    if (departmentFilter) params.set("department", departmentFilter)
    if (priceFilter !== "all") params.set("price", priceFilter)
    if (debouncedSearch) params.set("search", debouncedSearch)
    const next = params.toString()
    const current = searchParams.toString()
    if (next === current) return
    router.replace(next ? `/marketplace/assets?${next}` : "/marketplace/assets", { scroll: false })
  }, [debouncedSearch, departmentFilter, priceFilter, router, searchParams, typeFilter])

  useEffect(() => {
    syncFiltersToUrl()
  }, [syncFiltersToUrl])

  const swrKey = user
    ? (["marketplace-assets", typeFilter, departmentFilter, debouncedSearch] as const)
    : null

  const { data, error, isLoading, mutate } = useSWR(swrKey, () =>
    marketplaceApi.listAssets({
      assetType: typeFilter === "all" ? undefined : typeFilter,
      department: departmentFilter ?? undefined,
      search: debouncedSearch || undefined,
      limit: 100,
    }),
  )

  const includeFederated =
    (typeFilter === "all" || typeFilter === "connector_config") && !departmentFilter
  const federatedKey =
    user && includeFederated
      ? (["marketplace-federated-connectors", debouncedSearch] as const)
      : null
  const { data: federatedData } = useSWR(federatedKey, () =>
    marketplaceApi.listFederatedConnectors({
      search: debouncedSearch || undefined,
      limit: 100,
    }),
  )

  const { data: categories } = useSWR(user ? "marketplace-categories" : null, () => marketplaceApi.listCategories())

  const departmentFacets = useMemo(() => dedupeFacets(categories?.departments ?? []), [categories?.departments])

  /** Lookup of asset-type → count for badges on the type filter chips. */
  const typeCounts = useMemo(() => {
    const map = new Map<string, number>()
    for (const item of categories?.assetTypes ?? []) {
      map.set(item.key.trim().toLowerCase(), item.count)
    }
    return map
  }, [categories?.assetTypes])

  const activeDepartmentLabel = useMemo(() => {
    if (!departmentFilter) return null
    const match = departmentFacets.find((facet) => facet.key === departmentFilter)
    return (match?.key ?? departmentFilter).replace(/_/g, " ")
  }, [departmentFacets, departmentFilter])

  const assets = useMemo(() => {
    const catalog = data?.assets ?? []
    if (!includeFederated || !federatedData?.assets?.length) return catalog

    const linkedRegistryIds = new Set(
      catalog.map((asset) => asset.partnerRegistryId).filter((id): id is string => Boolean(id)),
    )
    const federatedExtras = federatedData.assets
      .filter((asset) => !linkedRegistryIds.has(asset.registryId ?? asset.id))
      .map(
        (asset): MarketplaceAssetSummary => ({
          ...asset,
          connectorChecklist: asset.connectorChecklist ?? [],
          connectorsReady: asset.connectorsReady ?? true,
          requiredConnectorsConnected: asset.requiredConnectorsConnected ?? 0,
          requiredConnectorsTotal: asset.requiredConnectorsTotal ?? 0,
          tags: asset.tags ?? [],
          canInstall: asset.canInstall ?? false,
          installed: asset.installed ?? false,
          federated: true,
          source: asset.source ?? "partner_registry",
        }),
      )
    return [...catalog, ...federatedExtras]
  }, [data?.assets, federatedData?.assets, includeFederated])

  useEffect(() => {
    const purchase = searchParams.get("purchase")
    const purchaseSlug = searchParams.get("slug")
    if (purchase !== "success" || !purchaseSlug || !assets.length) return
    const asset = assets.find((row) => row.slug === purchaseSlug)
    if (asset) {
      toast.success("Purchase complete", { description: "Continue with install into your workspace." })
      setInstallTarget(asset)
      setInstallOpen(true)
    }
    const params = new URLSearchParams(searchParams.toString())
    params.delete("purchase")
    params.delete("slug")
    const next = params.toString()
    router.replace(next ? `/marketplace/assets?${next}` : "/marketplace/assets", { scroll: false })
  }, [assets, router, searchParams])

  const visibleAssets = useMemo(() => {
    if (priceFilter === "all") return assets
    return assets.filter((asset) => (priceFilter === "free" ? isFreeAsset(asset) : !isFreeAsset(asset)))
  }, [assets, priceFilter])

  const openInstall = useCallback((asset: MarketplaceAssetSummary) => {
    setInstallTarget(asset)
    setInstallOpen(true)
  }, [])

  const openDetail = useCallback(
    (asset: MarketplaceAssetSummary) => {
      router.push(`/marketplace/assets/${encodeURIComponent(asset.slug)}`)
    },
    [router],
  )

  const handleClone = async (asset: MarketplaceAssetSummary) => {
    setBusy(`clone:${asset.id}`)
    try {
      const result = await marketplaceApi.cloneAsset(asset.slug)
      toast.success("Draft copy created", {
        description: `${result.asset.title} is saved as a private draft in your org.`,
      })
    } catch (err) {
      toast.error("Clone failed", {
        description: err instanceof Error ? err.message : "Try again",
      })
    } finally {
      setBusy(null)
    }
  }

  const emptyMessage = useMemo(() => {
    if (priceFilter === "free") return "No free assets match the current filters."
    if (priceFilter === "paid") return "No paid assets match the current filters."
    if (debouncedSearch) return "No assets match your search."
    if (departmentFilter) return `No assets in department "${departmentFilter.replace(/_/g, " ")}".`
    if (typeFilter !== "all") return "No assets in this category yet."
    if (categories?.totalAssets === 0) return "The catalog is empty right now. Check back soon for new assets."
    return "No assets found."
  }, [priceFilter, debouncedSearch, departmentFilter, typeFilter, categories?.totalAssets])

  return (
    <AppShell title="Marketplace">
      {/* shrink-0 keeps AppShell's flex-col <main> from compressing the catalog
         so the grid can scroll with the page instead of clipping. */}
      <div className="relative shrink-0 bg-[color:var(--g-canvas)]">
        <GravitrePageHeader
          eyebrow="Gravitre Marketplace"
          title="Install packs into your workspace"
          description="One click provisions agents, workflows, and knowledge — then we notify you with deep links to open them."
          icon={<Package className="h-5 w-5" />}
          actions={
            <div className="flex flex-col items-start gap-3 sm:items-end">
              <Button asChild size="sm">
                <Link href="/marketplace/installed">
                  View installed
                  <ChevronRight className="ml-1 h-4 w-4" aria-hidden />
                </Link>
              </Button>
              <nav className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[color:var(--g-text-muted)] sm:justify-end">
                <Link href="/marketplace/submit" className="transition-colors hover:text-foreground">
                  Partner submissions
                </Link>
                <Link href="/marketplace/connectors" className="transition-colors hover:text-foreground">
                  Partner connectors
                </Link>
                <Link href="/connectors" className="transition-colors hover:text-foreground">
                  Connectors
                </Link>
              </nav>
            </div>
          }
        />

        <div className="space-y-6 px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)] sm:py-5">
          <section className="grid grid-cols-2 gap-[var(--np-kpi-gap)] sm:grid-cols-3">
            <GravitreMetric
              label="Catalog packs"
              value={categories ? (categories.totalAssets ?? 0).toLocaleString() : "—"}
              hint="Published assets"
              icon={<Package className="h-4 w-4" />}
            />
            <GravitreMetric
              label="In view"
              value={isLoading ? "—" : visibleAssets.length}
              hint={activeDepartmentLabel ? activeDepartmentLabel : "Current filters"}
            />
            <GravitreMetric
              label="Installed (view)"
              value={isLoading ? "—" : visibleAssets.filter((a) => a.installed).length}
              hint="Among loaded results"
            />
          </section>

          {/* Toolbar: search + department + price, then type chips */}
          <GravitreSurface className="space-y-3 p-3 sm:p-4 md:p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
              <div className="relative min-w-0 flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search marketplace…"
                  className="rounded-[var(--np-radius-md)] pl-9"
                />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Select
                  value={departmentFilter ?? "all"}
                  onValueChange={(value) => setDepartmentFilter(value === "all" ? null : value)}
                >
                  <SelectTrigger className="w-full rounded-[var(--np-radius-md)] sm:w-[200px]" aria-label="Filter by department">
                    <SelectValue placeholder="All departments" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectLabel>Departments</SelectLabel>
                      <SelectItem value="all">All departments ({categories?.totalAssets ?? 0})</SelectItem>
                      {departmentFacets.map((facet) => (
                        <SelectItem key={facet.key} value={facet.key} className="capitalize">
                          {facet.key.replace(/_/g, " ")} ({facet.count})
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
                <SegmentedControl
                  options={PRICE_FILTERS}
                  value={priceFilter}
                  onChange={setPriceFilter}
                  ariaLabel="Filter by price"
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 border-t border-divide pt-3">
              {TYPE_FILTERS.map((filter) => (
                <FilterChip
                  key={filter.id}
                  label={filter.label}
                  active={typeFilter === filter.id}
                  onClick={() => setTypeFilter(filter.id)}
                  icon={"icon" in filter ? filter.icon : undefined}
                  count={filter.id === "all" ? categories?.totalAssets : typeCounts.get(filter.id)}
                />
              ))}
            </div>
          </GravitreSurface>

          {/* Result meta + clear */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-muted-foreground">
              {isLoading
                ? "Loading catalog…"
                : `${visibleAssets.length} ${visibleAssets.length === 1 ? "pack" : "packs"}`}
              {activeDepartmentLabel ? <span className="capitalize"> · {activeDepartmentLabel}</span> : null}
            </p>
            {typeFilter !== "all" || departmentFilter || priceFilter !== "all" || debouncedSearch ? (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setTypeFilter("all")
                  setDepartmentFilter(null)
                  setPriceFilter("all")
                  setSearch("")
                }}
              >
                Clear filters
              </Button>
            ) : null}
          </div>

          {isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
              {Array.from({ length: 8 }).map((_, index) => (
                <AssetCardSkeleton key={index} />
              ))}
            </div>
          ) : error ? (
            <GravitreSurface className="border-destructive/40 bg-destructive/5 text-sm text-destructive">
              <p className="font-medium">Failed to load marketplace catalog.</p>
              <p className="mt-1 text-destructive/80">
                {error instanceof Error && error.message.trim()
                  ? error.message
                  : "Check that the FastAPI backend is running and FASTAPI_BASE_URL points at it (local default: http://localhost:8000)."}
              </p>
            </GravitreSurface>
          ) : visibleAssets.length === 0 ? (
            <GravitreEmpty title={emptyMessage} hint="Adjust filters or clear search to see more packs." />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
              {visibleAssets.map((asset, index) => (
                <AssetCard
                  key={asset.id}
                  asset={asset}
                  index={index}
                  isAdmin={isAdmin}
                  busy={busy}
                  reduceMotion={reduceMotion}
                  onOpenDetail={openDetail}
                  onInstall={openInstall}
                  onClone={handleClone}
                />
              ))}
            </div>
          )}
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
