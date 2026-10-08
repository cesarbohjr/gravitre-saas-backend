"use client"

import { useRef, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { MarketplaceDecisionDialog } from "@/components/marketplace/marketplace-decision-dialog"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import {
  AssetPricingEditor,
  formatAssetPriceLabel,
} from "@/components/marketplace/asset-pricing-editor"
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
import {
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  Globe,
  Loader2,
  ShieldCheck,
  Sparkles,
  XCircle,
} from "lucide-react"
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
  runEdit,
}: {
  asset: MarketplaceAssetSummary
  busy: string | null
  onApprove: (asset: MarketplaceAssetSummary) => void
  onReject: (asset: MarketplaceAssetSummary) => void
  onPricingSaved: () => Promise<void>
  runEdit: (id: string, write: () => Promise<void>) => Promise<void>
}) {
  const [expanded, setExpanded] = useState(false)
  const {
    data: detailData,
    error: detailError,
    isLoading: detailLoading,
    mutate: refreshDetail,
  } = useSWR(
    expanded ? `marketplace-platform-review-${asset.slug}` : null,
    () => marketplaceApi.getPlatformReviewAsset(asset.slug),
  )
  const detail = detailData?.asset

  return (
    <div className="space-y-3 border-b border-[color:var(--g-border-subtle)] py-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold">{asset.title}</h3>
            <Badge variant="secondary">public review</Badge>
            <Badge variant="outline">{formatAssetType(asset.assetType)}</Badge>
            <Badge variant="outline">
              {formatAssetPriceLabel(asset.pricingType, asset.priceCents)}
            </Badge>
          </div>
          {asset.description ? (
            <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
              {asset.description}
            </p>
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
          {asset.businessOutcome ||
          asset.useCase ||
          asset.estimatedHoursSaved != null ? (
            <div className="mt-2 space-y-1 text-xs">
              {asset.businessOutcome ? (
                <p>
                  <span className="font-medium text-foreground">Outcome:</span>{" "}
                  {asset.businessOutcome}
                </p>
              ) : null}
              {asset.useCase ? (
                <p>
                  <span className="font-medium text-foreground">Use case:</span>{" "}
                  {asset.useCase}
                </p>
              ) : null}
              {asset.estimatedHoursSaved != null ? (
                <p>
                  <span className="font-medium text-foreground">
                    {ESTIMATED_HOURS_SAVED_MONTHLY}:
                  </span>{" "}
                  {asset.estimatedHoursSaved}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            disabled={Boolean(busy)}
            onClick={() => onApprove(asset)}
          >
            {busy === asset.id ? (
              <Loader2
                className="mr-1.5 h-3.5 w-3.5 animate-spin"
                aria-hidden
              />
            ) : (
              <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" aria-hidden />
            )}
            Approve
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={Boolean(busy)}
            onClick={() => onReject(asset)}
          >
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
        <ChevronDown
          className={`mr-1 h-3.5 w-3.5 transition-transform ${expanded ? "rotate-180" : ""}`}
          aria-hidden
        />
        {expanded ? "Hide config preview" : "Preview config"}
      </Button>
      {expanded && detailError ? (
        <WorkSectionErrorCard
          title="Could not refresh configuration"
          onRetry={() => void refreshDetail()}
        />
      ) : null}
      {expanded ? (
        detailLoading && !detail ? (
          <div className="h-24 animate-pulse rounded-lg border bg-muted/30" />
        ) : !detail ? null : detail?.config &&
          Object.keys(detail.config).length > 0 ? (
          <pre className="max-h-64 overflow-auto rounded-lg border bg-muted/20 p-3 text-xs">
            {JSON.stringify(detail.config, null, 2)}
          </pre>
        ) : (
          <p className="text-xs text-muted-foreground">
            No config payload to preview.
          </p>
        )
      ) : null}
      <AssetPricingEditor
        pricingType={asset.pricingType}
        priceCents={asset.priceCents}
        disabled={Boolean(busy)}
        onSave={async (payload) =>
          runEdit(asset.id, async () => {
            await marketplaceApi.updatePlatformAssetPricing(asset.slug, payload)
            toast.success("Pricing saved", { description: asset.title })
            await onPricingSaved()
          })
        }
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
  runEdit,
}: {
  asset: MarketplaceAssetSummary
  busy: string | null
  onToggleFeatured: (asset: MarketplaceAssetSummary, enabled: boolean) => void
  onToggleVerified: (asset: MarketplaceAssetSummary, enabled: boolean) => void
  onPricingSaved: () => Promise<void>
  runEdit: (id: string, write: () => Promise<void>) => Promise<void>
}) {
  return (
    <div className="space-y-4 border-b border-[color:var(--g-border-subtle)] py-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold">{asset.title}</h3>
            <Badge variant="outline">{formatAssetType(asset.assetType)}</Badge>
            <Badge variant="outline">
              {formatAssetPriceLabel(asset.pricingType, asset.priceCents)}
            </Badge>
            <AssetTrustBadges asset={asset} />
          </div>
          <p className="text-xs text-muted-foreground">{asset.slug}</p>
        </div>
        <div className="flex flex-col gap-3 sm:items-end">
          <div className="flex items-center gap-2">
            <Switch
              id={`featured-${asset.id}`}
              checked={Boolean(asset.featured)}
              disabled={Boolean(busy)}
              onCheckedChange={(enabled) => onToggleFeatured(asset, enabled)}
            />
            <Label
              htmlFor={`featured-${asset.id}`}
              className="inline-flex min-h-11 items-center gap-1 text-sm"
            >
              <Sparkles className="h-3.5 w-3.5" aria-hidden />
              Featured
            </Label>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              id={`verified-${asset.id}`}
              checked={Boolean(asset.verified)}
              disabled={Boolean(busy)}
              onCheckedChange={(enabled) => onToggleVerified(asset, enabled)}
            />
            <Label
              htmlFor={`verified-${asset.id}`}
              className="inline-flex min-h-11 items-center gap-1 text-sm"
            >
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
        onSave={async (payload) =>
          runEdit(asset.id, async () => {
            await marketplaceApi.updatePlatformAssetPricing(asset.slug, payload)
            toast.success("Pricing saved", { description: asset.title })
            await onPricingSaved()
          })
        }
      />
    </div>
  )
}

export default function MarketplacePlatformAdminPage() {
  const { user } = useAuth()
  const {
    data: me,
    error: roleError,
    isLoading: roleLoading,
    mutate: refreshRole,
  } = useSWR(user ? "/api/auth/me" : null, fetcher)
  const isPlatformAdmin = Boolean(
    (me as { platformAdmin?: boolean } | undefined)?.platformAdmin,
  )
  const lock = useRef(false)
  const [decision, setDecision] = useState<{
    asset: MarketplaceAssetSummary
    kind: "approve" | "archive"
  } | null>(null)
  const [rejectError, setRejectError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [rejectTarget, setRejectTarget] =
    useState<MarketplaceAssetSummary | null>(null)
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
    user && isPlatformAdmin
      ? ["marketplace-platform-catalog", catalogFilter]
      : null,
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

  const handleToggleFeatured = async (
    asset: MarketplaceAssetSummary,
    enabled: boolean,
  ) => {
    if (lock.current || !isPlatformAdmin) return
    lock.current = true
    setBusy(asset.id)
    try {
      await marketplaceApi.setPlatformAssetFeatured(asset.slug, enabled)
      toast.success(enabled ? "Added to featured" : "Removed from featured", {
        description: asset.title,
      })
      await Promise.allSettled([mutateCatalog()])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Featured update failed")
    } finally {
      lock.current = false
      setBusy(null)
    }
  }

  const handleToggleVerified = async (
    asset: MarketplaceAssetSummary,
    enabled: boolean,
  ) => {
    if (lock.current || !isPlatformAdmin) return
    lock.current = true
    setBusy(asset.id)
    try {
      await marketplaceApi.setPlatformAssetVerified(asset.slug, enabled)
      toast.success(enabled ? "Asset verified" : "Verification removed", {
        description: asset.title,
      })
      await Promise.allSettled([mutateCatalog()])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Verified update failed")
    } finally {
      lock.current = false
      setBusy(null)
    }
  }

  const runEdit = async (id: string, write: () => Promise<void>) => {
    if (lock.current) throw new Error("Another marketplace update is pending")
    lock.current = true
    setBusy(id)
    try {
      await write()
    } finally {
      lock.current = false
      setBusy(null)
    }
  }

  const handleApprove = async (asset: MarketplaceAssetSummary) => {
    if (lock.current || !isPlatformAdmin)
      throw new Error("Another marketplace decision is pending")
    lock.current = true
    setBusy(asset.id)
    try {
      const result = await marketplaceApi.approvePlatformAsset(asset.slug)
      if (!result.approved)
        throw new Error(
          "The server did not confirm publication. Review the asset before retrying.",
        )
      toast.success(`${asset.title} published to public catalog`)
      await Promise.allSettled([mutate(), mutateCatalog()])
    } catch (err) {
      throw err
    } finally {
      lock.current = false
      setBusy(null)
    }
  }

  const handleReject = async () => {
    if (!rejectTarget || lock.current) return
    const reason = rejectReason.trim()
    if (!reason) {
      toast.error("Rejection reason is required")
      return
    }
    lock.current = true
    setRejectError(null)
    setBusy(rejectTarget.id)
    try {
      await marketplaceApi.rejectPlatformAsset(rejectTarget.slug, reason)
      toast.success("Returned to draft")
      setRejectTarget(null)
      setRejectReason("")
      await Promise.allSettled([mutate(), mutateCatalog()])
    } catch (err) {
      setRejectError(
        err instanceof Error
          ? err.message
          : "Reject failed. Your feedback is retained.",
      )
    } finally {
      lock.current = false
      setBusy(null)
    }
  }

  if (roleLoading)
    return (
      <AppShell title="Platform review">
        <p role="status" className="p-6">
          Checking platform permissions…
        </p>
      </AppShell>
    )
  if (roleError && !me)
    return (
      <AppShell title="Platform review">
        <WorkSectionErrorCard
          title="Could not check platform permissions"
          onRetry={() => void refreshRole()}
        />
      </AppShell>
    )
  if (!isPlatformAdmin) {
    return (
      <AppShell title="Platform review">
        <div className="mx-auto max-w-lg rounded-lg border bg-card p-6 text-center text-sm text-muted-foreground">
          Platform admin access is required to review public marketplace
          submissions.
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title="Public catalog review">
      <div
        className="bg-[color:var(--g-canvas)] pb-24 [&_[data-slot=button]]:min-h-11"
        data-composition="operate"
      >
        <GravitrePageHeader
          title="Gravitre public review queue"
          description="Set paid pricing and review community submissions before they appear in the public catalog."
          icon={<Globe className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              {pendingTotal > 0 ? (
                <Badge variant="secondary">{pendingTotal} pending</Badge>
              ) : null}
              <Button variant="outline" size="sm" asChild>
                <Link href="/marketplace/assets">
                  <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
                  Marketplace
                </Link>
              </Button>
            </div>
          }
        />

        <div className="mx-auto max-w-4xl space-y-6 px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)] sm:py-5">
          {error ? (
            <WorkSectionErrorCard
              title="Could not refresh public review queue"
              message="Loaded submissions remain available."
              onRetry={() => void mutate()}
            />
          ) : null}
          {isLoading && !data ? (
            <div className="h-32 animate-pulse rounded-xl border bg-muted/40" />
          ) : !data ? null : pending.length === 0 ? (
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
                  onApprove={(asset) => setDecision({ asset, kind: "approve" })}
                  onReject={(asset) => {
                    setRejectTarget(asset)
                    setRejectReason("")
                    setRejectError(null)
                  }}
                  runEdit={runEdit}
                  onPricingSaved={async () => {
                    await Promise.allSettled([mutate(), mutateCatalog()])
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
                Feature assets on the marketplace home and manage catalog review
                badges. These badges do not verify runtime behavior.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {(["all", "featured", "verified"] as const).map((filter) => (
                  <Button
                    key={filter}
                    size="sm"
                    variant={catalogFilter === filter ? "default" : "outline"}
                    onClick={() => setCatalogFilter(filter)}
                  >
                    {filter === "all"
                      ? "All public"
                      : filter === "featured"
                        ? "Featured"
                        : "Verified"}
                  </Button>
                ))}
              </div>
            </header>

            {catalogError ? (
              <WorkSectionErrorCard
                title="Could not refresh catalog curation"
                message="Loaded assets remain available."
                onRetry={() => void mutateCatalog()}
              />
            ) : null}
            {catalogLoading && !catalogData ? (
              <div className="h-32 animate-pulse rounded-xl border bg-muted/40" />
            ) : !catalogData ? null : catalogAssets.length === 0 ? (
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
                    runEdit={runEdit}
                    onPricingSaved={async () => {
                      await Promise.allSettled([mutateCatalog()])
                    }}
                  />
                ))}
              </div>
            )}
          </section>
        </div>

        {decision ? (
          <MarketplaceDecisionDialog
            key={decision.asset.id}
            title={`Publish publicly: ${decision.asset.title}?`}
            description="This approval makes the submission visible in the public marketplace catalog. Review configuration and pricing before publishing."
            actionLabel="Confirm public publication"
            onCancel={() => setDecision(null)}
            onConfirm={() => handleApprove(decision.asset)}
          />
        ) : null}
        <Dialog
          open={Boolean(rejectTarget)}
          onOpenChange={(open) => {
            if (!open && !lock.current) setRejectTarget(null)
          }}
        >
          <DialogContent className="[&_[data-slot=button]]:min-h-11">
            <DialogHeader>
              <DialogTitle>Reject {rejectTarget?.title}</DialogTitle>
              <DialogDescription>
                The publisher will see this feedback and can revise before
                resubmitting.
              </DialogDescription>
            </DialogHeader>
            <label
              htmlFor="marketplace-reject-reason"
              className="text-sm font-medium"
            >
              Review feedback
            </label>
            <Textarea
              id="marketplace-reject-reason"
              disabled={Boolean(busy)}
              value={rejectReason}
              onChange={(event) => setRejectReason(event.target.value)}
              placeholder="What needs to change before this can go public?"
              rows={4}
            />
            {rejectError ? (
              <p role="alert" className="text-sm text-destructive">
                {rejectError}
              </p>
            ) : null}
            <DialogFooter>
              <Button
                variant="outline"
                disabled={Boolean(busy)}
                onClick={() => setRejectTarget(null)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={Boolean(busy)}
                onClick={handleReject}
              >
                Reject
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  )
}
