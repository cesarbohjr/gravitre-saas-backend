"use client"

import { Suspense, useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { AssetReviewsSection } from "@/components/marketplace/asset-reviews-section"
import { AssetTrustBadges } from "@/components/marketplace/asset-trust-badges"
import { DepartmentPipelineByDepartment } from "@/components/marketplace/department-pipeline-panel"
import { InstallStepperSheet } from "@/components/marketplace/install-experience"
import {
  ConnectorChecklist,
  EntitlementBadge,
  NonAdminPurchaseNotice,
  PackContentsPreview,
  PriceBadge,
  assetRequiresPurchase,
  formatAssetPrice,
} from "@/components/marketplace/marketplace-asset-commerce"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { ESTIMATED_HOURS_SAVED_MONTHLY } from "@/lib/outcome-labels"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Copy,
  Loader2,
  MoreHorizontal,
  ShoppingCart,
  Trash2,
} from "lucide-react"
import { toast } from "sonner"
import type {
  MarketplaceAssetDetail,
  MarketplaceInstallBlocker,
} from "@/types/api"

function BlockerList({ blockers }: { blockers: MarketplaceInstallBlocker[] }) {
  if (!blockers.length) return null
  return (
    <ul className="space-y-2 rounded-2xl border border-destructive/30 bg-destructive/5 p-3 text-sm">
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

function MarketplaceAssetDetailContent() {
  const params = useParams<{ slug: string }>()
  const router = useRouter()
  const searchParams = useSearchParams()
  const slug = decodeURIComponent(params.slug)
  const { user } = useAuth()
  const { isAdmin } = useOrgAdmin()
  const [installOpen, setInstallOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const { data, error, isLoading, mutate } = useSWR(
    user ? ["marketplace-asset", slug] : null,
    () => marketplaceApi.getAsset(slug),
  )
  const asset = data?.asset as MarketplaceAssetDetail | undefined

  const { data: entitlement, mutate: mutateEntitlement } = useSWR(
    user && asset ? ["marketplace-entitlement", slug] : null,
    () => marketplaceApi.assetEntitlement(slug),
  )

  useEffect(() => {
    const purchase = searchParams.get("purchase")
    if (!purchase) return
    if (purchase === "success") {
      toast.success("Purchase complete", { description: "You can install this asset now." })
      void mutateEntitlement()
      setInstallOpen(true)
    } else if (purchase === "cancelled") {
      toast.message("Checkout cancelled")
    } else if (purchase === "1") {
      setInstallOpen(true)
    }
    router.replace(`/marketplace/assets/${encodeURIComponent(slug)}`, { scroll: false })
  }, [mutateEntitlement, router, searchParams, slug])

  const needsPurchase = Boolean(
    asset && assetRequiresPurchase({ ...asset, hasEntitlement: entitlement?.hasEntitlement ?? asset.hasEntitlement }),
  )

  const handleClone = async () => {
    if (!asset) return
    setBusy(true)
    try {
      const result = await marketplaceApi.cloneAsset(asset.slug)
      toast.success("Draft copy created", { description: result.asset.title })
    } catch (err) {
      toast.error("Clone failed", { description: err instanceof Error ? err.message : "Try again" })
    } finally {
      setBusy(false)
    }
  }

  const handleUninstall = async () => {
    if (!asset || !isAdmin) return
    if (
      !window.confirm(
        `Uninstall "${asset.title}"? This removes the marketplace install record from your org.`,
      )
    ) {
      return
    }
    setBusy(true)
    try {
      await marketplaceApi.uninstallAsset(asset.slug)
      toast.success("Asset uninstalled")
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Uninstall failed")
    } finally {
      setBusy(false)
    }
  }

  const openInstall = useCallback(() => setInstallOpen(true), [])

  if (error) {
    return (
      <AppShell title="Asset not found">
        <div className="mx-auto max-w-2xl rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">Could not load this marketplace asset.</p>
          <Button className="mt-4" variant="outline" asChild>
            <Link href="/marketplace/assets">Back to catalog</Link>
          </Button>
        </div>
      </AppShell>
    )
  }

  const installLabel = asset
    ? needsPurchase
      ? `Buy & install · ${formatAssetPrice(asset)}`
      : asset.canInstall
        ? "Install to workspace"
        : "Connect apps to install"
    : "Install"

  return (
    <AppShell title={asset?.title ?? "Marketplace asset"}>
      <div className="relative shrink-0 bg-[color:var(--g-canvas)] pb-[calc(12rem+env(safe-area-inset-bottom))] md:pb-8" data-composition="discover">
        <section className="border-b border-[color:var(--g-border-subtle)] bg-[color:var(--g-rail-bg)] px-[var(--np-page-pad-sm)] pt-6 sm:px-[var(--np-page-pad)] sm:pt-8">
          <div className="mx-auto max-w-[760px]">
            <Button variant="ghost" size="sm" asChild className="-ml-2">
              <Link href="/marketplace/assets">
                <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
                Back to catalog
              </Link>
            </Button>
            <p className={cn(TYPE.eyebrow, "mt-3")}>Marketplace / Pack detail</p>
          </div>
        </section>

        <div className="mx-auto max-w-[760px] space-y-6 px-[var(--np-page-pad-sm)] py-5 sm:px-[var(--np-page-pad)]">
        {isLoading && !asset ? (
          <div className="space-y-4">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : asset ? (
          <>
            <header className="space-y-4">
              <div className="rounded-[10px] border border-[color:var(--g-border-default)] bg-background p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{asset.assetType.replace(/_/g, " ")}</Badge>
                  {asset.department ? <Badge variant="secondary">{asset.department}</Badge> : null}
                  <AssetTrustBadges asset={asset} />
                </div>
                <h1 className={cn(TYPE.pageTitle, "mt-3")}>{asset.title}</h1>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <PriceBadge asset={asset} className="text-sm" />
                  <EntitlementBadge
                    asset={{
                      ...asset,
                      hasEntitlement: entitlement?.hasEntitlement ?? asset.hasEntitlement,
                      requiresPayment: entitlement?.requiresPayment ?? asset.requiresPayment,
                    }}
                  />
                </div>
                {needsPurchase && isAdmin ? (
                  <p className="mt-2 text-sm text-muted-foreground">
                    One-time purchase ({formatAssetPrice(asset)}) unlocks install into your workspace.
                  </p>
                ) : null}
              </div>
              {asset.description ? (
                <p className="text-sm text-muted-foreground text-pretty">{asset.description}</p>
              ) : null}
              {asset.businessOutcome || asset.useCase || asset.estimatedHoursSaved != null ? (
                <div className="rounded-[10px] border border-[color:var(--g-border-default)] bg-background p-4 text-sm">
                  <p className="mb-2 text-xs font-medium text-muted-foreground">
                    Outcome
                  </p>
                  {asset.businessOutcome ? (
                    <p className="text-foreground">{asset.businessOutcome}</p>
                  ) : null}
                  <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                    {asset.useCase ? (
                      <div>
                        <dt className="text-xs text-muted-foreground">Use case</dt>
                        <dd>{asset.useCase}</dd>
                      </div>
                    ) : null}
                    {asset.estimatedHoursSaved != null ? (
                      <div>
                        <dt className="text-xs text-muted-foreground">{ESTIMATED_HOURS_SAVED_MONTHLY}</dt>
                        <dd>{asset.estimatedHoursSaved}h</dd>
                      </div>
                    ) : null}
                  </dl>
                </div>
              ) : null}
            </header>

            {asset.blockers?.length ? <BlockerList blockers={asset.blockers} /> : null}

            {asset.connectorChecklist?.length ? (
              <div className="rounded-[10px] border border-[color:var(--g-border-default)] bg-background p-4">
                <ConnectorChecklist items={asset.connectorChecklist} />
              </div>
            ) : null}

            <PackContentsPreview items={asset.packItems} linkChildren />

            {asset.department ? <DepartmentPipelineByDepartment department={asset.department} /> : null}

            {!isAdmin && needsPurchase ? <NonAdminPurchaseNotice /> : null}

            <div className="hidden flex-wrap gap-2 md:flex">
              {isAdmin && !asset.installed ? (
                <Button className="rounded-[10px] font-semibold" onClick={openInstall}>
                  {needsPurchase ? (
                    <>
                      <ShoppingCart className="mr-1.5 h-4 w-4" aria-hidden />
                      {installLabel}
                    </>
                  ) : (
                    installLabel
                  )}
                </Button>
              ) : null}
              {isAdmin ? (
                <Button variant="ghost" className="rounded-[10px]" disabled={busy} onClick={handleClone}>
                  {busy ? (
                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
                  ) : (
                    <Copy className="mr-1.5 h-3.5 w-3.5" aria-hidden />
                  )}
                  Clone draft
                </Button>
              ) : null}
              {asset.installed ? (
                <>
                  <Button className="rounded-[10px] font-semibold" asChild>
                    <Link href="/marketplace/installed">
                      <CheckCircle2 className="mr-1.5 h-4 w-4 text-success" aria-hidden />
                      Open installed
                    </Link>
                  </Button>
                  {isAdmin ? (
                    <Button variant="ghost" className="text-destructive" disabled={busy} onClick={handleUninstall}>
                      {busy ? (
                        <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
                      ) : (
                        <Trash2 className="mr-1.5 h-3.5 w-3.5" aria-hidden />
                      )}
                      Uninstall
                    </Button>
                  ) : null}
                </>
              ) : null}
            </div>

            <AssetReviewsSection
              assetRef={asset.slug}
              averageRating={asset.averageRating}
              reviewCount={asset.reviewCount}
              onStatsChange={() => void mutate()}
            />
          </>
        ) : null}
        </div>

        {asset && (isAdmin || asset.installed) ? (
          <div
            className="fixed inset-x-0 bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-20 border-t border-[color:var(--g-border-default)] bg-[color:var(--g-canvas)]/95 px-4 py-3 backdrop-blur-sm md:hidden"
            data-testid="marketplace-mobile-actions"
          >
            <div className="mx-auto flex max-w-[760px] items-center gap-2">
              {isAdmin && !asset.installed ? (
                <Button className="min-w-0 flex-1 rounded-[10px] font-semibold" onClick={openInstall}>
                  {needsPurchase ? (
                    <>
                      <ShoppingCart className="mr-1.5 h-4 w-4 shrink-0" aria-hidden />
                      <span className="truncate">{installLabel}</span>
                    </>
                  ) : (
                    <span className="truncate">{installLabel}</span>
                  )}
                </Button>
              ) : null}
              {asset.installed ? (
                <Button className="min-w-0 flex-1 rounded-[10px] font-semibold" asChild>
                  <Link href="/marketplace/installed">Open installed</Link>
                </Button>
              ) : null}
              {isAdmin ? (
                <Button variant="outline" className="shrink-0 rounded-[10px]" disabled={busy} onClick={handleClone}>
                  Clone
                </Button>
              ) : null}
              {isAdmin && asset.installed ? (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="outline"
                      size="icon"
                      className="shrink-0 rounded-[10px]"
                      aria-label="More asset actions"
                      disabled={busy}
                    >
                      {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <MoreHorizontal className="h-4 w-4" aria-hidden />}
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" side="top" className="z-50">
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      disabled={busy}
                      onSelect={() => {
                        void handleUninstall()
                      }}
                    >
                      <Trash2 className="mr-2 h-3.5 w-3.5" aria-hidden />
                      Uninstall
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>

      <InstallStepperSheet
        asset={asset ?? null}
        open={installOpen}
        onOpenChange={setInstallOpen}
        onComplete={() => void mutate()}
        isAdmin={isAdmin}
      />
    </AppShell>
  )
}

export default function MarketplaceAssetDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="grid min-h-[40vh] place-items-center text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
        </div>
      }
    >
      <MarketplaceAssetDetailContent />
    </Suspense>
  )
}
