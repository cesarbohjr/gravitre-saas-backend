"use client"

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitreEmpty } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { MarketplaceCatalogToolbar } from "@/components/marketplace/marketplace-catalog-toolbar"
import {
  MarketplaceOutcomeTiles,
  type OutcomeTile,
} from "@/components/marketplace/marketplace-outcome-tiles"
import { TYPE } from "@/lib/design-system"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { cn } from "@/lib/utils"
import {
  BookOpen,
  Bot,
  ChevronDown,
  ChevronRight,
  Loader2,
  MoreHorizontal,
  Package,
  Plug,
  Search,
  Star,
  Workflow,
} from "lucide-react"
import { toast } from "sonner"
import type {
  MarketplaceAssetSummary,
  MarketplaceFacetCount,
} from "@/types/api"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { AssetSaveButton } from "@/components/marketplace/asset-save-button"
import {
  PriceBadge,
  assetRequiresPurchase,
  formatAssetPrice,
  isFreeAsset,
} from "@/components/marketplace/marketplace-asset-commerce"
import { InstallStepperSheet } from "@/components/marketplace/install-experience"
import { ProviderLogo } from "@/components/gravitre/provider-logo"
import { getCategoryIcon } from "@/lib/marketplace-category-icons"
import { MarketplaceFeaturedOutcome } from "@/components/marketplace/marketplace-featured-outcome"
import { Illustration } from "@/components/gravitre/illustration"
const TYPE_FILTERS = [
  { id: "all", label: "All" },
  { id: "ai_agent", label: "Agents", icon: Bot },
  { id: "workflow", label: "Workflows", icon: Workflow },
  { id: "knowledge_pack", label: "Knowledge", icon: BookOpen },
  { id: "department_pack", label: "Packs", icon: Package },
  { id: "connector_config", label: "Connectors", icon: Plug },
  { id: "play", label: "Plays", icon: Workflow },
  { id: "outcome_pack", label: "Outcome packs", icon: Package },
  { id: "dataset_pack", label: "Datasets", icon: Package },
  { id: "dashboard_pack", label: "Dashboards", icon: Package },
  { id: "capability_package", label: "Skills & plugins", icon: Package },
] as const

const PRICE_FILTERS = [
  { id: "all", label: "All prices" },
  { id: "free", label: "Free" },
  { id: "paid", label: "Paid" },
] as const

type PriceFilter = (typeof PRICE_FILTERS)[number]["id"]

const PRIMARY_TYPES = new Set([
  "all",
  "department_pack",
  "ai_agent",
  "workflow",
  "connector_config",
])

const LISTING_TYPE_LABEL: Record<string, string> = {
  ai_agent: "Agent",
  workflow: "Workflow",
  knowledge_pack: "Knowledge",
  department_pack: "Department pack",
  connector_config: "Connector",
  play: "Play",
  outcome_pack: "Outcome pack",
  dataset_pack: "Dataset",
  dashboard_pack: "Dashboard",
  capability_package: "Skill or plugin",
}

/** Asset mark: vendor logo for partner connectors, role/kind glyph otherwise. */
function AssetMark({ asset }: { asset: MarketplaceAssetSummary }) {
  if (asset.assetType === "capability_package") {
    return (
      <Package
        className="mt-0.5 size-4 shrink-0 text-muted-foreground"
        aria-label="Skill or plugin"
      />
    )
  }
  if (asset.assetType === "connector_config") {
    const vendor = asset.vendor || asset.connectorChecklist?.[0]?.connectorType
    if (vendor)
      return (
        <ProviderLogo provider={vendor} size="sm" className="mt-0.5 shrink-0" />
      )
    return (
      <Plug
        className="mt-0.5 size-4 shrink-0 text-muted-foreground"
        aria-label="Partner connector"
      />
    )
  }
  const { icon: Icon, label } = getCategoryIcon(
    asset.assetType,
    asset.department,
    asset.title,
  )
  return (
    <Icon
      className="mt-0.5 size-4 shrink-0 text-muted-foreground"
      strokeWidth={1.75}
      aria-label={label}
      role="img"
    />
  )
}

/** Single-line summary of an asset's connector setup, shown on catalog cards. */
function capitalizeFirst(value: string): string {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : value
}

function connectorSummary(asset: MarketplaceAssetSummary): string {
  if (!asset.connectorChecklist) return "Setup requirements not reported"
  const total = asset.connectorChecklist.length
  if (total === 0) return "No setup required"
  const required = asset.requiredConnectorsTotal
  if (required == null)
    return `${total} app${total === 1 ? "" : "s"} · requirements not reported`
  const optional = total - required
  const parts: string[] = []
  if (required > 0) parts.push(`${required} required`)
  if (optional > 0) parts.push(`${optional} optional`)
  const detail = parts.length ? ` · ${parts.join(", ")}` : ""
  return `${total} app${total === 1 ? "" : "s"} to connect${detail}`
}

const CAPABILITY_NOUN: Record<string, [string, string]> = {
  agent: ["agent", "agents"],
  workflow: ["workflow", "workflows"],
  knowledge: ["knowledge base", "knowledge bases"],
  connector_config: ["connector setup", "connector setups"],
  department_pack: ["department pack", "department packs"],
  capability_package: ["skill/plugin", "skills/plugins"],
  play: ["play", "plays"],
  outcome_pack: ["outcome pack", "outcome packs"],
  dataset_pack: ["dataset pack", "dataset packs"],
  dashboard_pack: ["dashboard pack", "dashboard packs"],
}

/** What installing the asset adds to the workspace, from its catalogued contents only. */
function capabilitySummary(asset: MarketplaceAssetSummary): string {
  if (asset.assetType.endsWith("_pack") && !asset.packItems?.length)
    return "Pack contents not reported"
  const counts = new Map<string, number>()
  const items = asset.packItems ?? []
  if (items.length > 0) {
    for (const item of items)
      counts.set(
        item.child.assetType,
        (counts.get(item.child.assetType) ?? 0) + 1,
      )
  } else {
    counts.set(asset.assetType, 1)
  }
  return Array.from(counts.entries())
    .map(([type, count]) => {
      const [one, many] = CAPABILITY_NOUN[type] ?? [
        type.replace(/_/g, " "),
        `${type.replace(/_/g, " ")}s`,
      ]
      return `${count} ${count === 1 ? one : many}`
    })
    .join(", ")
}

/**
 * Merges facet counts whose labels are equivalent once normalized (casing,
 * spacing, separators), so e.g. "Operations" never appears twice in the rail.
 */
function dedupeFacets(items: MarketplaceFacetCount[]): MarketplaceFacetCount[] {
  const merged = new Map<string, MarketplaceFacetCount>()
  for (const item of items) {
    const norm = item.key
      .trim()
      .toLowerCase()
      .replace(/[\s_-]+/g, " ")
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

function AssetCardSkeleton() {
  return (
    <div className="flex h-56 flex-col gap-3 rounded-xl border border-[color:var(--g-border-subtle)] p-4">
      <div className="flex items-center gap-3">
        <Skeleton className="size-10 rounded-lg" />
        <Skeleton className="h-4 w-40" />
      </div>
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-2/3" />
      <Skeleton className="mt-auto h-9 w-full" />
    </div>
  )
}

function AssetCard({
  asset,
  isAdmin,
  busy,
  onOpenDetail,
  onInstall,
  onClone,
}: {
  asset: MarketplaceAssetSummary
  isAdmin: boolean
  busy: string | null
  onOpenDetail: (asset: MarketplaceAssetSummary) => void
  onInstall: (asset: MarketplaceAssetSummary) => void
  onClone: (asset: MarketplaceAssetSummary) => void
}) {
  const blocked = asset.connectorsReady === false && !asset.installed
  const needsPurchase = assetRequiresPurchase(asset)
  const showPrimaryAction = isAdmin && !asset.installed
  const adds = capabilitySummary(asset)
  const systems = asset.connectorChecklist ?? []
  const missing = systems.filter((item) => item.required && !item.connected).length
  const typeLabel =
    LISTING_TYPE_LABEL[asset.assetType] ??
    capitalizeFirst(asset.assetType.replace(/_/g, " "))
  const department = (asset.department ?? "All departments").replace(/_/g, " ")
  const readiness = asset.installed
    ? "Installed in this workspace"
    : !asset.connectorChecklist
      ? "Setup requirements not reported"
      : systems.length === 0
        ? "No setup required"
        : missing > 0
          ? `Connect ${missing} required app${missing === 1 ? "" : "s"}`
          : "Ready to install"

  return (
    <article
      className="group relative flex h-full flex-col rounded-xl border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-4 transition-colors duration-200 focus-within:border-[color:var(--g-text-muted)] hover:border-[color:var(--g-text-muted)]"
      data-testid="marketplace-pack-row"
    >
      <div className="flex items-start gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-2)] [&>*]:mt-0">
          <AssetMark asset={asset} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs text-muted-foreground">
            {typeLabel}
            <span aria-hidden> · </span>
            <span className="capitalize">{department}</span>
          </p>
          <h3 className="mt-0.5 text-[15px] font-semibold leading-snug tracking-[-0.01em] text-foreground">
            <button
              type="button"
              onClick={() => onOpenDetail(asset)}
              className="text-left after:absolute after:inset-0 after:rounded-xl focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring"
            >
              {asset.title}
            </button>
          </h3>
        </div>
        <PriceBadge asset={asset} className="relative z-10 shrink-0" />
      </div>

      {asset.description ? (
        <p className="mt-3 line-clamp-2 text-pretty text-[13px] leading-relaxed text-muted-foreground">
          {asset.description}
        </p>
      ) : null}
      <p className="mt-2 text-xs text-muted-foreground">
        Adds <span className="text-foreground">{adds}</span>
        {asset.averageRating != null ? (
          <span className="ml-2 inline-flex items-center gap-0.5">
            <Star className="size-3 fill-warning text-warning" aria-hidden />
            {asset.averageRating.toFixed(1)}
            <span className="sr-only"> average rating</span>
          </span>
        ) : null}
      </p>

      <div className="mt-auto pt-4">
        <div className="flex min-h-7 items-center gap-2 border-t border-[color:var(--g-border-subtle)] pt-3">
          {systems.length > 0 ? (
            <ul className="flex shrink-0 items-center" aria-label={capitalizeFirst(connectorSummary(asset))}>
              {systems.slice(0, 4).map((item, index) => (
                <li
                  key={item.connectorType}
                  className={cn(
                    "rounded-full bg-[color:var(--g-surface-1)] ring-2 ring-[color:var(--g-surface-1)]",
                    index > 0 && "-ml-1.5",
                    !item.connected && "opacity-60",
                  )}
                >
                  <ProviderLogo provider={item.connectorType} label={item.label} size="sm" />
                </li>
              ))}
              {systems.length > 4 ? (
                <li className="ml-1 text-xs tabular-nums text-muted-foreground">+{systems.length - 4}</li>
              ) : null}
            </ul>
          ) : null}
          <span
            className={cn(
              "min-w-0 truncate text-xs",
              missing > 0 && !asset.installed
                ? "text-warning"
                : "text-muted-foreground",
            )}
          >
            {readiness}
          </span>
        </div>

        <div className="relative z-10 mt-3 flex items-center gap-1.5">
          {showPrimaryAction ? (
            <Button
              size="sm"
              className="flex-1"
              disabled={Boolean(busy)}
              onClick={() => onInstall(asset)}
              title={blocked && !needsPurchase ? "Connect required apps first" : undefined}
            >
              {busy === asset.id
                ? "Installing…"
                : needsPurchase
                  ? `Buy & install · ${formatAssetPrice(asset)}`
                  : blocked
                    ? "Connect apps"
                    : "Install"}
            </Button>
          ) : asset.installed ? (
            <Button size="sm" variant="outline" className="flex-1" asChild>
              <Link href="/marketplace/installed">Manage install</Link>
            </Button>
          ) : (
            <Button size="sm" variant="outline" className="flex-1" onClick={() => onOpenDetail(asset)}>
              View details
            </Button>
          )}
          <AssetSaveButton slug={asset.slug} assetId={asset.id} size="icon" variant="ghost" className="size-11 md:size-9" />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="icon" variant="ghost" className="size-11 md:size-9" aria-label={`More actions for ${asset.title}`}>
                <MoreHorizontal className="size-4" aria-hidden />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuItem className="min-h-11 md:min-h-9" onSelect={() => onOpenDetail(asset)}>
                More about this pack
              </DropdownMenuItem>
              {isAdmin ? (
                <DropdownMenuItem
                  className="min-h-11 md:min-h-9"
                  disabled={Boolean(busy)}
                  onSelect={() => onClone(asset)}
                >
                  {busy === `clone:${asset.id}` ? "Cloning…" : "Clone as private draft"}
                </DropdownMenuItem>
              ) : null}
              {!isAdmin && needsPurchase ? (
                <>
                  <DropdownMenuSeparator />
                  <p className="px-2 py-1.5 text-xs text-muted-foreground">
                    Paid listing. An org admin completes the purchase.
                  </p>
                </>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </article>
  )
}

const OUTCOME_PATHS = [
  {
    label: "Run IT",
    department: "Operations",
    detail: "Service, security and operations",
    tone: "emerald",
  },
  {
    label: "Grow Revenue",
    department: "Sales",
    detail: "Pipeline, enrichment and follow-up",
    tone: "electric",
  },
  {
    label: "Market Smarter",
    department: "Marketing",
    detail: "Campaigns, signals and content",
    tone: "coral",
  },
  {
    label: "Serve Customers",
    department: "Customer Success",
    detail: "Risk, support and retention",
    tone: "emerald",
  },
] as const

function MarketplaceAssetsContent() {
  const { user } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const initialSlug = searchParams.get("slug")
  const initialType = searchParams.get("type")
  const initialDepartment = searchParams.get("department")
  const initialPrice = searchParams.get("price")
  const { isAdmin, loading: roleLoading } = useOrgAdmin()
  const validTypes = useMemo(
    () => new Set(TYPE_FILTERS.map((filter) => filter.id)),
    [],
  )
  const [typeFilter, setTypeFilter] = useState<string>(
    initialType &&
      validTypes.has(initialType as (typeof TYPE_FILTERS)[number]["id"])
      ? initialType
      : "all",
  )
  const [departmentFilter, setDepartmentFilter] = useState<string | null>(
    initialDepartment,
  )
  const [priceFilter, setPriceFilter] = useState<PriceFilter>(
    initialPrice === "free" || initialPrice === "paid" ? initialPrice : "all",
  )
  const [search, setSearch] = useState(searchParams.get("search") ?? "")
  const debouncedSearch = useDebouncedValue(search.trim())
  const cloneLock = useRef(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [installTarget, setInstallTarget] =
    useState<MarketplaceAssetSummary | null>(null)
  const [installOpen, setInstallOpen] = useState(false)

  usePublishGravitreAISelection(
    installTarget
      ? {
          kind: "marketplace_asset",
          id: installTarget.id,
          label: installTarget.title,
        }
      : null,
  )

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
    router.replace(
      next ? `/marketplace/assets?${next}` : "/marketplace/assets",
      { scroll: false },
    )
  }, [
    debouncedSearch,
    departmentFilter,
    priceFilter,
    router,
    searchParams,
    typeFilter,
  ])

  useEffect(() => {
    syncFiltersToUrl()
  }, [syncFiltersToUrl])

  useEffect(() => {
    if (!roleLoading && !isAdmin && typeFilter === "capability_package") {
      setTypeFilter("all")
    }
  }, [isAdmin, roleLoading, typeFilter])

  const swrKey = user
    ? ([
        "marketplace-assets",
        typeFilter,
        departmentFilter,
        debouncedSearch,
      ] as const)
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
    (typeFilter === "all" || typeFilter === "connector_config") &&
    !departmentFilter
  const federatedKey =
    user && includeFederated
      ? (["marketplace-federated-connectors", debouncedSearch] as const)
      : null
  const {
    data: federatedData,
    error: federatedError,
    mutate: refreshFederated,
  } = useSWR(federatedKey, () =>
    marketplaceApi.listFederatedConnectors({
      search: debouncedSearch || undefined,
      limit: 100,
    }),
  )

  const {
    data: categories,
    error: categoryError,
    mutate: refreshCategories,
  } = useSWR(user ? "marketplace-categories" : null, () =>
    marketplaceApi.listCategories(),
  )

  const departmentFacets = useMemo(
    () => dedupeFacets(categories?.departments ?? []),
    [categories?.departments],
  )

  /** Lookup of asset-type → count for badges on the type filter chips. */
  const typeCounts = useMemo(() => {
    const map = new Map<string, number>()
    for (const item of categories?.assetTypes ?? []) {
      map.set(item.key.trim().toLowerCase(), item.count)
    }
    return map
  }, [categories?.assetTypes])

  const typeOptions = useMemo(
    () =>
      TYPE_FILTERS.map((filter) => ({
        id: filter.id as string,
        label: filter.label as string,
        count:
          filter.id === "all"
            ? categories?.totalAssets
            : typeCounts.get(filter.id),
        primary: PRIMARY_TYPES.has(filter.id),
      })).filter(
        (option) =>
          (isAdmin || option.id !== "capability_package") &&
          (option.primary || Boolean(option.count) || typeFilter === option.id),
      ),
    [categories?.totalAssets, isAdmin, typeCounts, typeFilter],
  )

  const outcomeTiles = useMemo<OutcomeTile[]>(
    () =>
      OUTCOME_PATHS.map((path) => {
        const facet =
          departmentFacets.find(
            (item) => item.key.toLowerCase() === path.department.toLowerCase(),
          ) ??
          (path.label === "Run IT"
            ? departmentFacets.find((item) => item.key.toLowerCase() === "it")
            : undefined)
        return {
          label: path.label,
          detail: path.detail,
          tone: path.tone,
          department: facet?.key ?? path.department,
          count: facet?.count,
        }
      }),
    [departmentFacets],
  )

  const activeDepartmentLabel = useMemo(() => {
    if (!departmentFilter) return null
    const match = departmentFacets.find(
      (facet) => facet.key === departmentFilter,
    )
    return (match?.key ?? departmentFilter).replace(/_/g, " ")
  }, [departmentFacets, departmentFilter])

  const assets = useMemo(() => {
    const catalog = data?.assets ?? []
    if (!includeFederated || !federatedData?.assets?.length) return catalog

    const linkedRegistryIds = new Set(
      catalog
        .map((asset) => asset.partnerRegistryId)
        .filter((id): id is string => Boolean(id)),
    )
    const federatedExtras = federatedData.assets
      .filter((asset) => !linkedRegistryIds.has(asset.registryId ?? asset.id))
      .map(
        (asset): MarketplaceAssetSummary => ({
          ...asset,
          connectorChecklist: asset.connectorChecklist,
          connectorsReady: asset.connectorsReady,
          requiredConnectorsConnected: asset.requiredConnectorsConnected,
          requiredConnectorsTotal: asset.requiredConnectorsTotal,
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
      toast.info("Checkout returned", {
        description:
          "Installation will check your workspace entitlement before proceeding.",
      })
      setInstallTarget(asset)
      setInstallOpen(true)
    }
    const params = new URLSearchParams(searchParams.toString())
    params.delete("purchase")
    params.delete("slug")
    const next = params.toString()
    router.replace(
      next ? `/marketplace/assets?${next}` : "/marketplace/assets",
      { scroll: false },
    )
  }, [assets, router, searchParams])

  const visibleAssets = useMemo(() => {
    if (priceFilter === "all") return assets
    return assets.filter((asset) =>
      priceFilter === "free" ? isFreeAsset(asset) : !isFreeAsset(asset),
    )
  }, [assets, priceFilter])
  const discoveryAssets = useMemo(
    () => visibleAssets.filter((asset) => !asset.installed),
    [visibleAssets],
  )
  // Promote an existing outcome without manufacturing a featured badge or catalog entry.
  const featuredOutcome =
    discoveryAssets.find((asset) => asset.slug === "msp-operations-pack") ??
    discoveryAssets.find((asset) =>
      ["play", "outcome_pack", "department_pack"].includes(asset.assetType),
    )

  const installedInView = useMemo(
    () => visibleAssets.filter((asset) => asset.installed),
    [visibleAssets],
  )

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
    if (cloneLock.current || !isAdmin) return
    cloneLock.current = true
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
      cloneLock.current = false
      setBusy(null)
    }
  }

  const emptyMessage = useMemo(() => {
    if (priceFilter === "free")
      return "No free assets match the current filters."
    if (priceFilter === "paid")
      return "No paid assets match the current filters."
    if (debouncedSearch) return "No assets match your search."
    if (departmentFilter)
      return `No assets in department "${departmentFilter.replace(/_/g, " ")}".`
    if (typeFilter !== "all") return "No assets in this category yet."
    if (categories?.totalAssets === 0)
      return "The catalog is empty right now. Check back soon for new assets."
    return "No assets found."
  }, [
    priceFilter,
    debouncedSearch,
    departmentFilter,
    typeFilter,
    categories?.totalAssets,
  ])

  const hasFilters =
    typeFilter !== "all" ||
    Boolean(departmentFilter) ||
    priceFilter !== "all" ||
    Boolean(debouncedSearch)
  const clearFilters = () => {
    setTypeFilter("all")
    setDepartmentFilter(null)
    setPriceFilter("all")
    setSearch("")
  }

  return (
    <AppShell title="Marketplace">
      {/* shrink-0 keeps AppShell's flex-col <main> from compressing the catalog
         so the grid can scroll with the page instead of clipping. */}
      <div
        className="relative shrink-0 bg-[color:var(--g-canvas)] [&_[data-slot=button]]:min-h-11 md:[&_[data-slot=button]]:min-h-9"
        data-testid="marketplace-catalog-b"
        data-composition="discover"
      >
        <section className="border-b border-[color:var(--g-border-subtle)] px-[var(--np-page-pad-sm)] pb-8 pt-6 sm:px-[var(--np-page-pad)] sm:pt-9">
          <div className="mx-auto flex max-w-[1240px] flex-col gap-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
              <div className="max-w-2xl">
                <p className={TYPE.eyebrow}>Marketplace</p>
                <h1 className={cn(TYPE.pageTitle, "mt-2 text-balance")}>
                  Put Gravitre to work.
                </h1>
                <p className={cn(TYPE.pageLead, "mt-2 text-pretty")}>
                  Install ready-made outcomes: agents, workflows and knowledge,
                  wired to the apps you already use.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <AskGravitreSummonButton label="Find an outcome" prompt="Help me find a suitable outcome pack and inspect its required systems, permissions and reported readiness." />
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm" className="min-h-11 gap-1.5 md:min-h-8">
                      Manage
                      <ChevronDown className="size-3.5 text-muted-foreground" aria-hidden />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-60">
                    <DropdownMenuLabel className="text-xs font-medium text-muted-foreground">
                      Your workspace
                    </DropdownMenuLabel>
                    {[
                      { href: "/marketplace/installed", label: "Installed listings" },
                      { href: "/marketplace/saved", label: "Saved for later" },
                      ...(isAdmin
                        ? [{ href: "/marketplace/capabilities", label: "Skills & plugins" }]
                        : []),
                    ].map((link) => (
                      <DropdownMenuItem key={link.href} asChild className="min-h-11 md:min-h-9">
                        <Link href={link.href}>{link.label}</Link>
                      </DropdownMenuItem>
                    ))}
                    <DropdownMenuSeparator />
                    <DropdownMenuLabel className="text-xs font-medium text-muted-foreground">
                      Partners
                    </DropdownMenuLabel>
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
            </div>

            <div className="relative max-w-2xl">
              <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <Input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search agents, workflows, packs and apps"
                aria-label="Search marketplace"
                className="h-12 rounded-xl border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] pl-11 text-[15px]"
              />
            </div>

            {!isLoading && !error && featuredOutcome && !hasFilters ? (
              <MarketplaceFeaturedOutcome asset={featuredOutcome} onPreview={openDetail} />
            ) : null}

            <div>
              <h2 className="text-[13px] font-semibold text-foreground">Start from an outcome</h2>
              <div className="mt-3">
                <MarketplaceOutcomeTiles
                  tiles={outcomeTiles}
                  activeDepartment={departmentFilter}
                  onSelect={setDepartmentFilter}
                />
              </div>
            </div>
          </div>
        </section>

        <div className="mx-auto max-w-[1240px] px-[var(--np-page-pad-sm)] py-6 sm:px-[var(--np-page-pad)]">
          <MarketplaceCatalogToolbar
            types={typeOptions}
            typeValue={typeFilter}
            onTypeChange={setTypeFilter}
            departments={departmentFacets}
            departmentValue={departmentFilter}
            onDepartmentChange={setDepartmentFilter}
            priceValue={priceFilter}
            onPriceChange={setPriceFilter}
            hasFilters={hasFilters}
            onClear={clearFilters}
          />

          <div className="mt-5 flex flex-col gap-8">
            {error || federatedError || categoryError ? (
              <div
                role="alert"
                className="flex flex-col items-start gap-2 border-l-2 border-[color:var(--g-warmth)] pl-4 text-sm"
              >
                <p>
                  Some catalog data could not be refreshed. Loaded assets remain
                  available.
                </p>
                <Button
                  variant="outline"
                  onClick={() =>
                    void Promise.allSettled([
                      mutate(),
                      refreshFederated(),
                      refreshCategories(),
                    ])
                  }
                >
                  Retry catalog
                </Button>
              </div>
            ) : null}

            {isLoading && !data ? (
              <div
                data-review-surface="marketplace-discovery"
                className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
              >
                {Array.from({ length: 6 }).map((_, index) => (
                  <AssetCardSkeleton key={index} />
                ))}
              </div>
            ) : !data && !federatedData ? null : visibleAssets.length === 0 ? (
              <GravitreEmpty
                illustration="moment-focus-time"
                title={emptyMessage}
                hint="Adjust filters or clear search to see more listings."
              />
            ) : (
              <>
                <section
                  data-review-surface="marketplace-discovery"
                  aria-labelledby="marketplace-discovery-heading"
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <h2 id="marketplace-discovery-heading" className={TYPE.sectionTitle}>
                      Catalog
                    </h2>
                    <p className={TYPE.meta}>
                      {discoveryAssets.length}{" "}
                      {discoveryAssets.length === 1 ? "listing" : "listings"}
                      {activeDepartmentLabel ? (
                        <span className="capitalize"> · {activeDepartmentLabel}</span>
                      ) : null}
                    </p>
                  </div>
                  {discoveryAssets.length === 0 ? (
                    <div className="mt-3 text-center">
                      <Illustration name="moment-all-clear" width={140} className="mx-auto mb-3" />
                      <p className="text-sm text-muted-foreground">
                        Everything matching these filters is already installed.
                      </p>
                    </div>
                  ) : (
                    <div
                      className="mt-3 grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
                      data-testid="marketplace-scan-list"
                    >
                      {discoveryAssets.map((asset) => (
                        <AssetCard
                          key={asset.id}
                          asset={asset}
                          isAdmin={isAdmin}
                          busy={busy}
                          onOpenDetail={openDetail}
                          onInstall={openInstall}
                          onClone={handleClone}
                        />
                      ))}
                    </div>
                  )}
                </section>
                {installedInView.length > 0 ? (
                  <section data-review-surface="marketplace-ops">
                    <div className="flex items-baseline justify-between gap-3">
                      <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-foreground">
                        Installed in this workspace
                      </h2>
                      <Link
                        href="/marketplace/installed"
                        className="inline-flex min-h-11 items-center gap-1 text-[13px] font-medium text-[color:var(--g-emerald)] hover:underline md:min-h-0"
                      >
                        Manage all
                        <ChevronRight className="size-3.5" aria-hidden />
                      </Link>
                    </div>
                    <ul className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                      {installedInView.map((asset) => (
                        <li key={asset.id}>
                          <button
                            type="button"
                            onClick={() => openDetail(asset)}
                            className="flex min-h-14 w-full items-center gap-3 rounded-lg border border-[color:var(--g-border-subtle)] px-3 text-left transition-colors hover:border-[color:var(--g-text-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          >
                            <AssetMark asset={asset} />
                            <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
                              {asset.title}
                            </span>
                            <span className="text-xs text-[color:var(--g-emerald)]">Installed</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </section>
                ) : null}
              </>
            )}
          </div>
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
