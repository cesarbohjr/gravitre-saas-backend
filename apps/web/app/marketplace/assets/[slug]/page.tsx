"use client"

import { Suspense, useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { AssetReviewsSection } from "@/components/marketplace/asset-reviews-section"
import { AssetTrustBadges } from "@/components/marketplace/asset-trust-badges"
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
import {
  Activity,
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  Copy,
  Gauge,
  Loader2,
  ShieldCheck,
  ShoppingCart,
  Sparkles,
  Trash2,
} from "lucide-react"
import { toast } from "sonner"
import type {
  MarketplaceAssetDetail,
  MarketplaceAssetSummary,
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

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {}
}

function asRecords(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item)) : []
}

function asStrings(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : []
}

function OutcomePackContract({ asset }: { asset: MarketplaceAssetDetail }) {
  if (asset.assetType !== "outcome_pack") return null

  const config = asRecord(asset.config)
  const contract = asRecord(config.outcome_contract)
  const plays = asRecords(config.plays)
  const kpis = asRecords(contract.kpis)
  const profiles = asRecords(config.runtime_profiles)
  const successCriteria = asStrings(contract.success_criteria)
  const tags = new Set((asset.tags ?? []).map((tag) => tag.toLowerCase()))
  const productionVerified =
    tags.has("production-verified") ||
    (profiles.length > 0 && profiles.every((profile) => profile.status === "production_verified"))
  const outcomeVerified = tags.has("outcome-verified")
  const certification = outcomeVerified ? "Outcome verified" : productionVerified ? "Production verified" : "Compatible"

  return (
    <section className="space-y-4 rounded-xl border bg-muted/10 p-4" data-testid="marketplace3-outcome-contract">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Marketplace 3.0 operating capability</p>
          <h2 className="mt-1 text-lg font-semibold text-foreground">Measurable outcome contract</h2>
        </div>
        <Badge variant="outline" className="gap-1.5">
          <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
          {certification}
        </Badge>
      </div>

      {typeof contract.target_outcome === "string" && contract.target_outcome ? (
        <div>
          <p className="text-xs font-medium text-muted-foreground">Target outcome</p>
          <p className="mt-1 text-sm text-foreground">{contract.target_outcome}</p>
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border bg-background/70 p-3">
          <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
            <Activity className="h-3.5 w-3.5" aria-hidden />
            Plays
          </div>
          <p className="mt-1 text-xl font-semibold text-foreground">{plays.length}</p>
          <p className="text-xs text-muted-foreground">Jobs Gravitre can operate</p>
        </div>
        <div className="rounded-lg border bg-background/70 p-3">
          <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
            <Gauge className="h-3.5 w-3.5" aria-hidden />
            KPIs
          </div>
          <p className="mt-1 text-xl font-semibold text-foreground">{kpis.length}</p>
          <p className="text-xs text-muted-foreground">Metrics tied to outcomes</p>
        </div>
        <div className="rounded-lg border bg-background/70 p-3">
          <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
            Verification
          </div>
          <p className="mt-1 text-sm font-semibold text-foreground">Source of record</p>
          <p className="text-xs text-muted-foreground">Provider acceptance is not completion</p>
        </div>
      </div>

      {plays.length ? (
        <div>
          <p className="text-xs font-medium text-muted-foreground">Included Plays</p>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {plays.map((play, index) => (
              <div key={String(play.key ?? index)} className="min-w-0 rounded-lg border bg-background/60 p-3">
                <p className="truncate text-sm font-medium text-foreground">{String(play.name ?? play.key ?? "Play")}</p>
                {typeof play.description === "string" ? (
                  <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">{play.description}</p>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {kpis.length ? (
        <div>
          <p className="text-xs font-medium text-muted-foreground">Measured KPIs</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {kpis.map((kpi, index) => {
              const direction = String(kpi.direction ?? "")
              const suffix = direction === "increase" ? " ↑" : direction === "decrease" ? " ↓" : ""
              return (
                <Badge key={String(kpi.key ?? index)} variant="secondary">
                  {String(kpi.label ?? kpi.key ?? "KPI")}{suffix}
                </Badge>
              )
            })}
          </div>
        </div>
      ) : null}

      {successCriteria.length ? (
        <div>
          <p className="text-xs font-medium text-muted-foreground">Success criteria</p>
          <ul className="mt-2 space-y-1.5 text-sm text-foreground">
            {successCriteria.map((criterion) => (
              <li key={criterion} className="flex gap-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden />
                <span>{criterion}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
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

  return (
    <AppShell title={asset?.title ?? "Marketplace asset"}>
      <div className="mx-auto max-w-3xl space-y-6">
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link href="/marketplace/assets">
            <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
            Back to catalog
          </Link>
        </Button>

        {isLoading && !asset ? (
          <div className="space-y-4">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : asset ? (
          <>
            <header className="space-y-4">
              <div className="rounded-xl border bg-muted/20 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{asset.assetType.replace(/_/g, " ")}</Badge>
                  {asset.department ? <Badge variant="secondary">{asset.department}</Badge> : null}
                  <AssetTrustBadges asset={asset} />
                </div>
                <h1 className="mt-3 text-2xl font-semibold text-foreground">{asset.title}</h1>
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
                <div className="rounded-lg border bg-muted/20 p-4 text-sm">
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
              <div className="rounded-lg border bg-muted/20 p-4">
                <ConnectorChecklist items={asset.connectorChecklist} />
              </div>
            ) : null}

            <OutcomePackContract asset={asset} />

            <PackContentsPreview items={asset.packItems} linkChildren />

            {!isAdmin && needsPurchase ? <NonAdminPurchaseNotice /> : null}

            <div className="flex flex-wrap gap-2">
              {isAdmin && !asset.installed ? (
                <Button className="rounded-full font-semibold" onClick={openInstall}>
                  {needsPurchase ? (
                    <>
                      <ShoppingCart className="mr-1.5 h-4 w-4" aria-hidden />
                      {`Buy & install · ${formatAssetPrice(asset)}`}
                    </>
                  ) : asset.canInstall ? (
                    <>
                      <Sparkles className="mr-1.5 h-4 w-4" aria-hidden />
                      Install to workspace
                    </>
                  ) : (
                    "Connect apps to install"
                  )}
                </Button>
              ) : null}
              {isAdmin ? (
                <Button variant="ghost" className="rounded-full" disabled={busy} onClick={handleClone}>
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
                  <Button className="rounded-full font-semibold" asChild>
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
