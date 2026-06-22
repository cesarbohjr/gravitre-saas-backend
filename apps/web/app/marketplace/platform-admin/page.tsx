"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { AssetPricingEditor, formatAssetPriceLabel } from "@/components/marketplace/asset-pricing-editor"
import { AssetTrustBadges } from "@/components/marketplace/asset-trust-badges"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { fetcher } from "@/lib/fetcher"
import { ESTIMATED_HOURS_SAVED_MONTHLY } from "@/lib/outcome-labels"
import { ArrowLeft, CheckCircle2, ChevronDown, Globe, Loader2, ShieldCheck, Sparkles, XCircle } from "lucide-react"
import { toast } from "sonner"
import type { MarketplaceAssetSummary } from "@/types/api"

function formatAssetType(assetType: string) {
  return assetType.replace(/_/g, " ")
}

function QueueRow({
  asset,
  busy,
  onApprove,
  onReject,
  onPricingSaved,
}: {
  asset: MarketplaceAssetSummary
  busy: string | null
  onApprove: (asset: MarketplaceAssetSummary) => void
  onReject: (asset: MarketplaceAssetSummary) => void
  onPricingSaved: () => Promise<void>
}) {
  const [expanded, setExpanded] = useState(false)
  const { data: detailData, isLoading: detailLoading } = useSWR(
    expanded ? `marketplace-platform-review-${asset.slug}` : null,
    () => marketplaceApi.getPlatformReviewAsset(asset.slug),
  )
  const detail = detailData?.asset

  return (
    <div className="space-y-3 rounded-xl border border-border bg-card p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold">{asset.title}</h3>
            <Badge variant="secondary">public review</Badge>
            <Badge variant="outline">{formatAssetType(asset.assetType)}</Badge>
            <Badge variant="outline">{formatAssetPriceLabel(asset.pricingType, asset.priceCents)}</Badge>
          </div>
          {asset.description ? (
            <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{asset.description}</p>
          ) : null}
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span>{asset.slug}</span>
            {asset.orgId ? <span>Org {asset.orgId.slice(0, 8)}…</span> : null}
            {asset.publisherDisplayName ? (
              <span>
                Publisher {asset.publisherDisplayName}
                {asset.publisherSlug ? ` (@${asset.publisherSlug})` : ""}
              </span>
            ) : null}
          </div>
          {asset.businessOutcome || asset.useCase || asset.estimatedHoursSaved != null ? (
            <div className="mt-2 space-y-1 text-xs">
              {asset.businessOutcome ? (
                <p>
                  <span className="font-medium text-foreground">Outcome:</span> {asset.businessOutcome}
                </p>
              ) : null}
              {asset.useCase ? (
                <p>
                  <span className="font-medium text-foreground">Use case:</span> {asset.useCase}
                </p>
              ) : null}
              {asset.estimatedHoursSaved != null ? (
                <p>
                  <span className="font-medium text-foreground">{ESTIMATED_HOURS_SAVED_MONTHLY}:</span>{" "}
                  {asset.estimatedHoursSaved}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" disabled={Boolean(busy)} onClick={() => onApprove(asset)}>
            {busy === asset.id ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
            ) : (
              <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" aria-hidden />
            )}
            Approve
          </Button>
          <Button size="sm" variant="outline" disabled={Boolean(busy)} onClick={() => onReject(asset)}>
            <XCircle className="mr-1.5 h-3.5 w-3.5" aria-hidden />
            Reject
          </Button>
        </div>
      </div>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-8 px-2 text-xs text-muted-foreground"
        onClick={() => setExpanded((value) => !value)}
      >
        <ChevronDown className={`mr-1 h-3.5 w-3.5 transition-transform ${expanded ? "rotate-180" : ""}`} aria-hidden />
        {expanded ? "Hide config preview" : "Preview config"}
      </Button>
      {expanded ? (
        detailLoading && !detail ? (
          <div className="h-24 animate-pulse rounded-lg border bg-muted/30" />
        ) : detail?.config && Object.keys(detail.config).length > 0 ? (
          <pre className="max-h-64 overflow-auto rounded-lg border bg-muted/20 p-3 text-xs">
            {JSON.stringify(detail.config, null, 2)}
          </pre>
        ) : (
          <p className="text-xs text-muted-foreground">No config payload to preview.</p>
        )
      ) : null}
      <AssetPricingEditor
        pricingType={asset.pricingType}
        priceCents={asset.priceCents}
        disabled={Boolean(busy)}
        onSave={async (payload) => {
          await marketplaceApi.updatePlatformAssetPricing(asset.slug, payload)
          toast.success("Pricing saved", { description: asset.title })
          await onPricingSaved()
        }}
      />
    </div>
  )
}

type CatalogFilter = "all" | "featured" | "verified"

function CurationRow({
  asset,
  busy,
  onToggleFeatured,
  onToggleVerified,
  onPricingSaved,
}: {
  asset: MarketplaceAssetSummary
  busy: string | null
  onToggleFeatured: (asset: MarketplaceAssetSummary, enabled: boolean) => void
  onToggleVerified: (asset: MarketplaceAssetSummary, enabled: boolean) => void
  onPricingSaved: () => Promise<void>
}) {
  return (
    <div className="space-y-4 rounded-xl border border-border bg-card p-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold">{asset.title}</h3>
            <Badge variant="outline">{formatAssetType(asset.assetType)}</Badge>
            <Badge variant="outline">{formatAssetPriceLabel(asset.pricingType, asset.priceCents)}</Badge>
            <AssetTrustBadges asset={asset} />
          </div>
          <p className="text-xs text-muted-foreground">{asset.slug}</p>
        </div>
        <div className="flex flex-col gap-3 sm:items-end">
          <div className="flex items-center gap-2">
            <Switch
              id={`featured-${asset.id}`}
              checked={Boolean(asset.featured)}
              disabled={busy === asset.id}
              onCheckedChange={(enabled) => onToggleFeatured(asset, enabled)}
            />
            <Label htmlFor={`featured-${asset.id}`} className="inline-flex items-center gap-1 text-sm">
              <Sparkles className="h-3.5 w-3.5" aria-hidden />
              Featured
            </Label>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              id={`verified-${asset.id}`}
              checked={Boolean(asset.verified)}
              disabled={busy === asset.id}
              onCheckedChange={(enabled) => onToggleVerified(asset, enabled)}
            />
            <Label htmlFor={`verified-${asset.id}`} className="inline-flex items-center gap-1 text-sm">
              <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
              Verified
            </Label>
          </div>
        </div>
      </div>
      <AssetPricingEditor
        pricingType={asset.pricingType}
        priceCents={asset.priceCents}
        disabled={Boolean(busy)}
        onSave={async (payload) => {
          await marketplaceApi.updatePlatformAssetPricing(asset.slug, payload)
          toast.success("Pricing saved", { description: asset.title })
          await onPricingSaved()
        }}
      />
    </div>
  )
}

export default function MarketplacePlatformAdminPage() {
  const { user } = useAuth()
  const { data: me } = useSWR(user ? "/api/auth/me" : null, fetcher)
  const isPlatformAdmin = Boolean((me as { platformAdmin?: boolean } | undefined)?.platformAdmin)
  const [busy, setBusy] = useState<string | null>(null)
  const [rejectTarget, setRejectTarget] = useState<MarketplaceAssetSummary | null>(null)
  const [rejectReason, setRejectReason] = useState("")
  const [catalogFilter, setCatalogFilter] = useState<CatalogFilter>("all")

  const { data, error, isLoading, mutate } = useSWR(
    user && isPlatformAdmin ? "marketplace-platform-queue" : null,
    () => marketplaceApi.listPlatformReviewQueue({ limit: 100 }),
  )

  const {
    data: catalogData,
    error: catalogError,
    isLoading: catalogLoading,
    mutate: mutateCatalog,
  } = useSWR(
    user && isPlatformAdmin ? ["marketplace-platform-catalog", catalogFilter] : null,
    () =>
      marketplaceApi.listPlatformCatalog({
        limit: 100,
        featured: catalogFilter === "featured" ? true : undefined,
        verified: catalogFilter === "verified" ? true : undefined,
      }),
  )

  const pending = data?.assets ?? []
  const pendingTotal = data?.total ?? pending.length
  const catalogAssets = catalogData?.assets ?? []
  const catalogTotal = catalogData?.total ?? catalogAssets.length

  const handleToggleFeatured = async (asset: MarketplaceAssetSummary, enabled: boolean) => {
    setBusy(asset.id)
    try {
      await marketplaceApi.setPlatformAssetFeatured(asset.slug, enabled)
      toast.success(enabled ? "Added to featured" : "Removed from featured", {
        description: asset.title,
      })
      await mutateCatalog()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Featured update failed")
    } finally {
      setBusy(null)
    }
  }

  const handleToggleVerified = async (asset: MarketplaceAssetSummary, enabled: boolean) => {
    setBusy(asset.id)
    try {
      await marketplaceApi.setPlatformAssetVerified(asset.slug, enabled)
      toast.success(enabled ? "Asset verified" : "Verification removed", {
        description: asset.title,
      })
      await mutateCatalog()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Verified update failed")
    } finally {
      setBusy(null)
    }
  }

  const handleApprove = async (asset: MarketplaceAssetSummary) => {
    setBusy(asset.id)
    try {
      await marketplaceApi.approvePlatformAsset(asset.slug)
      toast.success(`${asset.title} published to public catalog`)
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Approve failed")
    } finally {
      setBusy(null)
    }
  }

  const handleReject = async () => {
    if (!rejectTarget) return
    const reason = rejectReason.trim()
    if (!reason) {
      toast.error("Rejection reason is required")
      return
    }
    setBusy(rejectTarget.id)
    try {
      await marketplaceApi.rejectPlatformAsset(rejectTarget.slug, reason)
      toast.success("Returned to draft")
      setRejectTarget(null)
      setRejectReason("")
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Reject failed")
    } finally {
      setBusy(null)
    }
  }

  if (!isPlatformAdmin) {
    return (
      <AppShell title="Platform review">
        <div className="mx-auto max-w-lg rounded-lg border bg-card p-6 text-center text-sm text-muted-foreground">
          Platform admin access is required to review public marketplace submissions.
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title="Public catalog review">
      <div className="mx-auto max-w-4xl space-y-6">
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link href="/marketplace">
            <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
            Marketplace
          </Link>
        </Button>

        <header>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <Globe className="h-5 w-5 text-primary" aria-hidden />
            Gravitre public review queue
            {pendingTotal > 0 ? (
              <Badge variant="secondary" className="ml-1">
                {pendingTotal} pending
              </Badge>
            ) : null}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Set paid pricing and review community submissions before they appear in the public catalog.
          </p>
        </header>

        {isLoading && !data ? (
          <div className="h-32 animate-pulse rounded-xl border bg-muted/40" />
        ) : error ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            Could not load public review queue.
          </div>
        ) : pending.length === 0 ? (
          <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
            No public assets awaiting review.
          </div>
        ) : (
          <div className="space-y-3">
            {pending.map((asset) => (
              <QueueRow
                key={asset.id}
                asset={asset}
                busy={busy}
                onApprove={handleApprove}
                onReject={setRejectTarget}
                onPricingSaved={async () => {
                  await mutate()
                }}
              />
            ))}
          </div>
        )}

        <section className="space-y-4 border-t pt-8">
          <header>
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <Sparkles className="h-5 w-5 text-primary" aria-hidden />
              Catalog curation
              {catalogTotal > 0 ? (
                <Badge variant="secondary" className="ml-1">
                  {catalogTotal} public
                </Badge>
              ) : null}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Feature assets on the marketplace home and award verified badges beyond publisher status.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {(["all", "featured", "verified"] as const).map((filter) => (
                <Button
                  key={filter}
                  size="sm"
                  variant={catalogFilter === filter ? "default" : "outline"}
                  onClick={() => setCatalogFilter(filter)}
                >
                  {filter === "all" ? "All public" : filter === "featured" ? "Featured" : "Verified"}
                </Button>
              ))}
            </div>
          </header>

          {catalogLoading && !catalogData ? (
            <div className="h-32 animate-pulse rounded-xl border bg-muted/40" />
          ) : catalogError ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
              Could not load public catalog for curation.
            </div>
          ) : catalogAssets.length === 0 ? (
            <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
              No published public assets match this filter.
            </div>
          ) : (
            <div className="space-y-3">
              {catalogAssets.map((asset) => (
                <CurationRow
                  key={asset.id}
                  asset={asset}
                  busy={busy}
                  onToggleFeatured={handleToggleFeatured}
                  onToggleVerified={handleToggleVerified}
                  onPricingSaved={async () => {
                    await mutateCatalog()
                  }}
                />
              ))}
            </div>
          )}
        </section>
      </div>

      <Dialog open={Boolean(rejectTarget)} onOpenChange={(open) => !open && setRejectTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject {rejectTarget?.title}</DialogTitle>
            <DialogDescription>
              The publisher will see this feedback and can revise before resubmitting.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={rejectReason}
            onChange={(event) => setRejectReason(event.target.value)}
            placeholder="What needs to change before this can go public?"
            rows={4}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectTarget(null)}>
              Cancel
            </Button>
            <Button variant="destructive" disabled={Boolean(busy)} onClick={handleReject}>
              Reject
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}
