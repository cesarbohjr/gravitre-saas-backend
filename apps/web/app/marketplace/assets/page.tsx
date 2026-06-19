"use client"

import { Suspense, useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { motion, useReducedMotion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { MarketplaceFacetSidebar } from "@/components/marketplace/marketplace-facet-sidebar"
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
  Star,
  Workflow,
} from "lucide-react"
import { toast } from "sonner"
import { toastMarketplaceInstallFailure } from "@/lib/marketplace-install-error"
import type {
  MarketplaceAssetInstallCheck,
  MarketplaceAssetSummary,
  MarketplaceConnectorChecklistItem,
  MarketplaceInstallBlocker,
} from "@/types/api"
import { CategoryIconChip } from "@/components/marketplace/category-icon-chip"
import { AssetSaveButton } from "@/components/marketplace/asset-save-button"
import type { AssetCategory } from "@/lib/marketplace-category-icons"

const TYPE_FILTERS = [
  { id: "all", label: "All" },
  { id: "ai_agent", label: "Agents", icon: Bot },
  { id: "workflow", label: "Workflows", icon: Workflow },
  { id: "knowledge_pack", label: "Knowledge", icon: Database },
  { id: "department_pack", label: "Department packs", icon: Package },
] as const

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

function checklistTone(item: MarketplaceConnectorChecklistItem) {
  if (item.connected) return "text-success"
  if (item.required) return "text-destructive"
  return "text-warning"
}

function ConnectorChecklist({ items }: { items: MarketplaceConnectorChecklistItem[] }) {
  if (!items.length) return null
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item.connectorType} className="flex items-start justify-between gap-2 text-sm">
          <div className="flex items-center gap-2">
            {item.connected ? (
              <CheckCircle2 className={cn("h-4 w-4 shrink-0", checklistTone(item))} aria-hidden />
            ) : (
              <Plug className={cn("h-4 w-4 shrink-0", checklistTone(item))} aria-hidden />
            )}
            <span className={cn(!item.connected && item.required && "font-medium")}>
              {item.label || item.connectorType}
              {item.required ? "" : " (optional)"}
            </span>
          </div>
          {!item.connected ? (
            <Button size="sm" variant="outline" asChild>
              <Link href={item.action_url || item.connectPath}>Connect</Link>
            </Button>
          ) : null}
        </li>
      ))}
    </ul>
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
        {asset.installed ? <Badge variant="secondary">Installed</Badge> : null}
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

      {asset.connectorChecklist?.length ? (
        <div className="mb-4 rounded-lg border border-border/60 bg-muted/20 p-3">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Connector checklist
          </p>
          <ConnectorChecklist items={asset.connectorChecklist} />
        </div>
      ) : null}

      <div className="mt-auto flex flex-wrap gap-2">
        <Button size="sm" variant="ghost" onClick={() => onOpenDetail(asset)}>
          Details
          <ChevronRight className="ml-1 h-3.5 w-3.5" aria-hidden />
        </Button>
        {isAdmin && !asset.installed ? (
          <Button size="sm" disabled={Boolean(busy)} onClick={() => onInstall(asset)} title={blocked ? "Connect required apps first" : undefined}>
            {busy === asset.id ? (
              <>
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
                Installing…
              </>
            ) : blocked ? (
              "Connect apps first"
            ) : (
              "Install"
            )}
          </Button>
        ) : null}
        <Button size="sm" variant="secondary" disabled={Boolean(busy)} onClick={() => onClone(asset)}>
          {busy === `clone:${asset.id}` ? (
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
          ) : (
            <Copy className="mr-1.5 h-3.5 w-3.5" aria-hidden />
          )}
          Clone
        </Button>
      </div>
    </motion.article>
  )
}

function InstallStepperSheet({
  asset,
  open,
  onOpenChange,
  onComplete,
}: {
  asset: MarketplaceAssetSummary | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onComplete: () => void
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
  const initialCategory = searchParams.get("category")
  const reduceMotion = useReducedMotion()
  const role = user?.role
  const isAdmin = role === "admin" || role === "owner"
  const validTypes = useMemo(() => new Set(TYPE_FILTERS.map((filter) => filter.id)), [])
  const [typeFilter, setTypeFilter] = useState<string>(
    initialType && validTypes.has(initialType as (typeof TYPE_FILTERS)[number]["id"]) ? initialType : "all",
  )
  const [departmentFilter, setDepartmentFilter] = useState<string | null>(initialDepartment)
  const [categoryFilter, setCategoryFilter] = useState<string | null>(initialCategory)
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
    if (categoryFilter) params.set("category", categoryFilter)
    if (debouncedSearch) params.set("search", debouncedSearch)
    const next = params.toString()
    const current = searchParams.toString()
    if (next === current) return
    router.replace(next ? `/marketplace/assets?${next}` : "/marketplace/assets", { scroll: false })
  }, [categoryFilter, debouncedSearch, departmentFilter, router, searchParams, typeFilter])

  useEffect(() => {
    syncFiltersToUrl()
  }, [syncFiltersToUrl])

  const swrKey = user
    ? (["marketplace-assets", typeFilter, departmentFilter, categoryFilter, debouncedSearch] as const)
    : null

  const { data, error, isLoading, mutate } = useSWR(swrKey, () =>
    marketplaceApi.listAssets({
      assetType: typeFilter === "all" ? undefined : typeFilter,
      department: departmentFilter ?? undefined,
      category: categoryFilter ?? undefined,
      search: debouncedSearch || undefined,
      limit: 100,
    }),
  )

  const { data: categories } = useSWR(user ? "marketplace-categories" : null, () => marketplaceApi.listCategories())

  const assets = data?.assets ?? []

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
    if (debouncedSearch) return "No assets match your search."
    if (departmentFilter) return `No assets in department "${departmentFilter.replace(/_/g, " ")}".`
    if (categoryFilter) return `No assets in category "${categoryFilter.replace(/_/g, " ")}".`
    if (typeFilter !== "all") return "No assets in this category yet."
    if (categories?.totalAssets === 0) return "The starter catalog is empty. Run backend/scripts/seed_marketplace.py."
    return "No assets found."
  }, [debouncedSearch, departmentFilter, categoryFilter, typeFilter, categories?.totalAssets])

  return (
    <AppShell title="Marketplace">
      <div className="relative overflow-hidden rounded-2xl border bg-card/40 p-6 md:p-8">
        <GridPattern className="opacity-40" />
        <div className="relative flex flex-col gap-6 lg:flex-row">
          {categories ? (
            <MarketplaceFacetSidebar
              className="hidden lg:block"
              totalAssets={categories.totalAssets}
              departments={categories.departments}
              categories={categories.categories}
              activeDepartment={departmentFilter}
              activeCategory={categoryFilter}
              onDepartmentChange={setDepartmentFilter}
              onCategoryChange={setCategoryFilter}
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
              {typeFilter !== "all" || departmentFilter || categoryFilter || debouncedSearch ? (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setTypeFilter("all")
                    setDepartmentFilter(null)
                    setCategoryFilter(null)
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
                departments={categories.departments.slice(0, 6)}
                categories={categories.categories.slice(0, 6)}
                activeDepartment={departmentFilter}
                activeCategory={categoryFilter}
                onDepartmentChange={setDepartmentFilter}
                onCategoryChange={setCategoryFilter}
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
                Failed to load marketplace catalog.
              </div>
            ) : assets.length === 0 ? (
              <div className="rounded-lg border border-dashed p-10 text-center text-sm text-muted-foreground">{emptyMessage}</div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {assets.map((asset, index) => (
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
