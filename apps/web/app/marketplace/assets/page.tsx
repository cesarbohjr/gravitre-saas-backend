"use client"

import { Suspense, useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { motion, useReducedMotion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { MarketplaceFacetSidebar } from "@/components/marketplace/marketplace-facet-sidebar"
import { AssetPurchaseButton } from "@/components/marketplace/asset-purchase-button"
import { AssetTrustBadges } from "@/components/marketplace/asset-trust-badges"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { GridPattern } from "@/components/gravitre/premium-effects"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { cn } from "@/lib/utils"
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  ChevronRight,
  Copy,
  Database,
  ExternalLink,
  Loader2,
  Package,
  Plug,
  Search,
  ShoppingCart,
  Star,
  Workflow,
} from "lucide-react"
import { toast } from "sonner"
import { toastMarketplaceInstallFailure } from "@/lib/marketplace-install-error"
import type {
  MarketplaceAssetInstallCheck,
  MarketplaceAssetSummary,
  MarketplaceFacetCount,
  MarketplaceInstallBlocker,
} from "@/types/api"
import { CategoryIconChip } from "@/components/marketplace/category-icon-chip"
import { AssetSaveButton } from "@/components/marketplace/asset-save-button"
import {
  ConnectorChecklist,
  EntitlementBadge,
  NonAdminPurchaseNotice,
  PackContentsPreview,
  PriceBadge,
  assetRequiresPurchase,
  formatAssetPrice,
  isFreeAsset,
} from "@/components/marketplace/marketplace-asset-commerce"
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

type InstallStep = "check" | "confirm" | "installing" | "done"

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

function BlockerList({ blockers }: { blockers: MarketplaceInstallBlocker[] }) {
  if (!blockers.length) return null
  return (
    <ul className="space-y-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm">
      {blockers.map((blocker) => (
        <li key={blocker.connector} className="flex items-start gap-2">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden />
          <div className="flex-1">
            <p>{blocker.reason}</p>
            {blocker.action_url ? (
              <Link href={blocker.action_url} className="text-primary underline-offset-4 hover:underline">
                Connect {blocker.connector}
              </Link>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  )
}

function AssetCardSkeleton() {
  return (
    <div className="flex h-full flex-col rounded-xl border bg-card p-5 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <Skeleton className="h-10 w-10 rounded-lg" />
          <div className="space-y-2">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-20" />
          </div>
        </div>
        <Skeleton className="h-9 w-9 rounded-full" />
      </div>
      <Skeleton className="mb-4 h-12 w-full" />
      <Skeleton className="mb-4 h-16 w-full rounded-lg" />
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
      transition={{ duration: 0.35, delay: reduceMotion ? 0 : index * 0.04 }}
      className={cn(
        "flex h-full flex-col rounded-xl border bg-card p-5 shadow-sm transition-shadow hover:shadow-md",
        asset.installed ? "border-success/30" : "border-border",
      )}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
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
            <h3 className="font-semibold leading-tight">{asset.title}</h3>
            <p className="text-xs text-muted-foreground">{asset.department ?? asset.assetType}</p>
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

      <div className="mt-auto flex flex-wrap gap-2">
        {showPrimaryAction ? (
          <Button
            size="sm"
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
                {`Buy · ${formatAssetPrice(asset)}`}
              </>
            ) : blocked ? (
              "Connect apps first"
            ) : (
              "Install"
            )}
          </Button>
        ) : null}
        <Button size="sm" variant={showPrimaryAction ? "outline" : "default"} onClick={() => onOpenDetail(asset)}>
          Details
          <ChevronRight className="ml-1 h-3.5 w-3.5" aria-hidden />
        </Button>
        {isAdmin ? (
          <Button size="sm" variant="ghost" disabled={Boolean(busy)} onClick={() => onClone(asset)}>
            {busy === `clone:${asset.id}` ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
            ) : (
              <Copy className="mr-1.5 h-3.5 w-3.5" aria-hidden />
            )}
            Clone draft
          </Button>
        ) : null}
      </div>
    </motion.article>
  )
}

function InstallStepperSheet({
  asset,
  open,
  onOpenChange,
  onComplete,
  isAdmin,
}: {
  asset: MarketplaceAssetSummary | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onComplete: () => void
  isAdmin: boolean
}) {
  const [step, setStep] = useState<InstallStep>("check")
  const [installResult, setInstallResult] = useState<Record<string, unknown> | null>(null)

  const checkKey = open && asset ? ["marketplace-install-check", asset.id] : null
  const { data: check, isLoading: checkLoading, mutate: refreshCheck } = useSWR(
    checkKey,
    () => marketplaceApi.installCheck(asset!.id),
    { revalidateOnFocus: false },
  )

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      setStep("check")
      setInstallResult(null)
    }
    onOpenChange(next)
  }

  const activeStep: InstallStep =
    step === "installing" || step === "done"
      ? step
      : step === "check" && check && !checkLoading
        ? check.canInstall
          ? "confirm"
          : "check"
        : step

  const runInstall = async () => {
    if (!asset) return
    setStep("installing")
    try {
      const result = await marketplaceApi.installAsset(asset.slug)
      setInstallResult(result.entities ?? {})
      setStep("done")
      onComplete()
      toast.success(`${asset.title} installed`)
    } catch (err) {
      toastMarketplaceInstallFailure(err, {
        blockerActionUrl: check?.blockers?.[0]?.action_url,
      })
      await refreshCheck()
      setStep("check")
    }
  }

  const checklist = check?.connectorChecklist ?? asset?.connectorChecklist ?? []
  const blockers = check?.blockers ?? []

  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent side="right" className="flex w-full flex-col sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Install {asset?.title ?? "asset"}</SheetTitle>
          <SheetDescription>Provision agents, workflows, and knowledge into your org.</SheetDescription>
        </SheetHeader>

        <div className="flex-1 space-y-4 overflow-y-auto px-4">
          <ol className="flex gap-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            {(["check", "confirm", "done"] as const).map((id, idx) => (
              <li
                key={id}
                className={cn(
                  "flex items-center gap-1",
                  (activeStep === id || (step === "installing" && id === "confirm") || (activeStep === "done" && id === "done")) &&
                    "text-primary",
                )}
              >
                <span className="grid h-5 w-5 place-items-center rounded-full border text-[10px]">{idx + 1}</span>
                {id}
              </li>
            ))}
          </ol>

          {checkLoading ? (
            <div className="grid place-items-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" aria-hidden />
            </div>
          ) : null}

          {!checkLoading && activeStep === "check" && !check?.canInstall ? (
            <>
              <BlockerList blockers={blockers} />
              <ConnectorChecklist items={checklist} />
              {check?.requiresPayment && !check?.hasEntitlement && asset && isAdmin ? (
                <AssetPurchaseButton asset={asset} check={check} onPurchased={() => void refreshCheck()} />
              ) : null}
            </>
          ) : null}

          {!checkLoading && (activeStep === "confirm" || step === "installing") ? (
            <>
              <p className="text-sm text-muted-foreground">All required connectors are connected. Confirm to install into your workspace.</p>
              <ConnectorChecklist items={checklist} />
            </>
          ) : null}

          {activeStep === "done" ? (
            <div className="space-y-3 rounded-lg border border-success/30 bg-success/5 p-4 text-sm">
              <p className="flex items-center gap-2 font-medium text-success">
                <CheckCircle2 className="h-4 w-4" aria-hidden />
                Installation complete
              </p>
              {installResult?.workflowId ? (
                <Button size="sm" variant="outline" asChild>
                  <Link href={`/workflows/${String(installResult.workflowId)}/builder`}>
                    Open workflow
                    <ExternalLink className="ml-1.5 h-3.5 w-3.5" aria-hidden />
                  </Link>
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>

        <SheetFooter className="border-t pt-4">
          {activeStep === "check" && !check?.canInstall ? (
            <Button variant="outline" onClick={() => handleOpenChange(false)}>
              Close
            </Button>
          ) : null}
          {activeStep === "confirm" ? (
            <>
              <Button variant="outline" onClick={() => handleOpenChange(false)}>
                Cancel
              </Button>
              <Button onClick={runInstall}>Confirm install</Button>
            </>
          ) : null}
          {step === "installing" ? (
            <Button disabled>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
              Installing…
            </Button>
          ) : null}
          {activeStep === "done" ? (
            <Button onClick={() => handleOpenChange(false)}>Done</Button>
          ) : null}
        </SheetFooter>
      </SheetContent>
    </Sheet>
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
  const role = user?.role
  const isAdmin = role === "admin" || role === "owner"
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
      {/* shrink-0 stops the AppShell's flex-col <main> from compressing this
         wrapper to the viewport height. Without it, the grid overflows but is
         clipped by overflow-hidden (used for the decorative grid pattern),
         which silently kills page scroll and cuts off cards. */}
      <div className="relative shrink-0 overflow-hidden rounded-2xl border bg-card/40 p-6 md:p-8">
        <GridPattern className="opacity-40" />
        <div className="relative flex flex-col gap-6 lg:flex-row">
          {categories ? (
            <MarketplaceFacetSidebar
              className="hidden lg:block"
              totalAssets={categories.totalAssets}
              departments={departmentFacets}
              activeDepartment={departmentFilter}
              onDepartmentChange={setDepartmentFilter}
            />
          ) : null}

          <div className="min-w-0 flex-1 space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Link href="/marketplace" className="hover:text-foreground">
                  Marketplace home
                </Link>
                <span aria-hidden>·</span>
                <Link href="/marketplace/installed" className="hover:text-foreground">
                  Installed
                </Link>
                <span aria-hidden>·</span>
                <Link href="/marketplace/submit" className="hover:text-foreground">
                  Partner submissions
                </Link>
                <span aria-hidden>·</span>
                <Link href="/marketplace/connectors" className="hover:text-foreground">
                  Partner connectors
                </Link>
                <span aria-hidden>·</span>
                <Link href="/connectors" className="hover:text-foreground">
                  Connectors
                </Link>
              </div>
              <div className="relative w-full md:max-w-sm">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search marketplace…"
                  className="pl-9"
                />
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              {TYPE_FILTERS.map((filter) => (
                <Button
                  key={filter.id}
                  size="sm"
                  variant={typeFilter === filter.id ? "default" : "outline"}
                  onClick={() => setTypeFilter(filter.id)}
                >
                  {filter.label}
                </Button>
              ))}
              <div
                role="group"
                aria-label="Filter by price"
                className="ml-auto inline-flex items-center gap-0.5 rounded-lg border p-0.5"
              >
                {PRICE_FILTERS.map((filter) => (
                  <button
                    key={filter.id}
                    type="button"
                    aria-pressed={priceFilter === filter.id}
                    onClick={() => setPriceFilter(filter.id)}
                    className={cn(
                      "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                      priceFilter === filter.id
                        ? "bg-primary/10 text-primary"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {filter.label}
                  </button>
                ))}
              </div>
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

            {categories ? (
              <MarketplaceFacetSidebar
                className="lg:hidden"
                totalAssets={categories.totalAssets}
                departments={departmentFacets.slice(0, 6)}
                activeDepartment={departmentFilter}
                onDepartmentChange={setDepartmentFilter}
              />
            ) : null}

            {isLoading ? (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {Array.from({ length: 6 }).map((_, index) => (
                  <AssetCardSkeleton key={index} />
                ))}
              </div>
            ) : error ? (
              <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
                <p className="font-medium">Failed to load marketplace catalog.</p>
                <p className="mt-1 text-destructive/80">
                  {error instanceof Error && error.message.trim()
                    ? error.message
                    : "Check that the FastAPI backend is running and FASTAPI_BASE_URL points at it (local default: http://localhost:8000)."}
                </p>
              </div>
            ) : visibleAssets.length === 0 ? (
              <div className="rounded-lg border border-dashed p-10 text-center text-sm text-muted-foreground">{emptyMessage}</div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
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
