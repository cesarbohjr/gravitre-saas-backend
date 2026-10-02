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
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  Copy,
  Loader2,
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

type OutcomePackPresentation = {
  plays: Array<{ key: string; name: string; description?: string; outcomeEvents: string[] }>
  kpis: Array<{ key: string; label: string; unit?: string; direction?: string }>
  successCriteria: string[]
  runtimeProviders: Array<{ provider: string; status: string }>
}

function outcomePackPresentation(asset: MarketplaceAssetDetail): OutcomePackPresentation | null {
  if (asset.assetType !== "outcome_pack" || !asset.config) return null
  const config = asset.config
  const contract = config.outcome_contract
  const rawPlays = config.plays
  const rawProfiles = config.runtime_profiles
  if (!contract || typeof contract !== "object" || !Array.isArray(rawPlays)) return null
  const contractRecord = contract as Record<string, unknown>
  const rawKpis = Array.isArray(contractRecord.kpis) ? contractRecord.kpis : []
  return {
    plays: rawPlays
      .filter((row): row is Record<string, unknown> => Boolean(row && typeof row === "object"))
      .map((row) => ({
        key: String(row.key ?? ""),
        name: String(row.name ?? row.key ?? "Play"),
        description: typeof row.description === "string" ? row.description : undefined,
        outcomeEvents: Array.isArray(row.outcome_events) ? row.outcome_events.map(String) : [],
      })),
    kpis: rawKpis
      .filter((row): row is Record<string, unknown> => Boolean(row && typeof row === "object"))
      .map((row) => ({
        key: String(row.key ?? ""),
        label: String(row.label ?? row.key ?? "KPI"),
        unit: typeof row.unit === "string" ? row.unit : undefined,
        direction: typeof row.direction === "string" ? row.direction : undefined,
      })),
    successCriteria: Array.isArray(contractRecord.success_criteria)
      ? contractRecord.success_criteria.map(String)
      : [],
    runtimeProviders: Array.isArray(rawProfiles)
      ? rawProfiles
          .filter((row): row is Record<string, unknown> => Boolean(row && typeof row === "object"))
          .map((row) => ({ provider: String(row.provider ?? ""), status: String(row.status ?? "") }))
      : [],
  }
}

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

  const outcomePack = asset ? outcomePackPresentation(asset) : null

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

            {outcomePack ? (
              <div className="grid gap-4 lg:grid-cols-2">
                <section className="rounded-xl border bg-muted/20 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2 className="text-sm font-semibold">What Gravitre operates</h2>
                    <Badge variant="secondary">Marketplace 3.0 · {outcomePack.plays.length} Plays</Badge>
                  </div>
                  <div className="mt-3 space-y-3">
                    {outcomePack.plays.map((play) => (
                      <div key={play.key} className="min-w-0">
                        <p className="text-sm font-medium text-foreground">{play.name}</p>
                        {play.description ? (
                          <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{play.description}</p>
                        ) : null}
                        {play.outcomeEvents.length ? (
                          <p className="mt-1 text-[11px] text-muted-foreground">
                            Outcome · {play.outcomeEvents.join(", ")}
                          </p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </section>

                <section className="rounded-xl border bg-muted/20 p-4">
                  <h2 className="text-sm font-semibold">How value is measured</h2>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    {outcomePack.kpis.map((kpi) => (
                      <div key={kpi.key} className="rounded-lg border bg-background/70 p-3">
                        <p className="text-xs font-medium text-foreground">{kpi.label}</p>
                        <p className="mt-1 text-[11px] text-muted-foreground">
                          {kpi.unit ?? "metric"}{kpi.direction ? ` · target: ${kpi.direction}` : ""}
                        </p>
                      </div>
                    ))}
                  </div>
                  {outcomePack.successCriteria.length ? (
                    <div className="mt-4">
                      <p className="text-xs font-medium text-muted-foreground">Verification contract</p>
                      <ul className="mt-2 space-y-1.5 text-xs text-foreground">
                        {outcomePack.successCriteria.map((criterion) => (
                          <li key={criterion} className="flex gap-2">
                            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" aria-hidden />
                            <span>{criterion}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {outcomePack.runtimeProviders.length ? (
                    <div className="mt-4 flex flex-wrap gap-1.5">
                      {outcomePack.runtimeProviders.map((profile) => (
                        <Badge key={`${profile.provider}:${profile.status}`} variant="outline">
                          {profile.provider.replace(/_/g, " ")} · {profile.status.replace(/_/g, " ")}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                </section>
              </div>
            ) : null}

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
