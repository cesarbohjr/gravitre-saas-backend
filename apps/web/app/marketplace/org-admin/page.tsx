"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitreEmpty,
  GravitreMetric,
  GravitrePageHeader,
  GravitreSurface,
} from "@/components/gravitre/nodus-product"
import { AssetOutcomeEditor } from "@/components/marketplace/asset-outcome-editor"
import { AssetPricingEditor, formatAssetPriceLabel } from "@/components/marketplace/asset-pricing-editor"
import { AssetVersionHistory } from "@/components/marketplace/asset-version-history"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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
import { useOrgAdmin } from "@/lib/use-org-admin"
import { ArrowLeft, CheckCircle2, Globe, Loader2, PlusCircle, Send, Shield, Trash2, XCircle } from "lucide-react"
import { toast } from "sonner"
import type { MarketplaceAssetSummary } from "@/types/api"

function OrgAssetRow({
  asset,
  busy,
  onApprove,
  onReject,
  onSubmit,
  onSubmitPublic,
  onArchive,
  onPricingSaved,
  showReviewActions,
  showDraftActions,
  showVersionHistory,
  showPublishedPricing,
  canSubmitPublic,
}: {
  asset: MarketplaceAssetSummary
  busy: string | null
  onApprove?: (asset: MarketplaceAssetSummary) => void
  onReject?: (asset: MarketplaceAssetSummary) => void
  onSubmit?: (asset: MarketplaceAssetSummary) => void
  onSubmitPublic?: (asset: MarketplaceAssetSummary) => void
  onArchive?: (asset: MarketplaceAssetSummary) => void
  onPricingSaved: () => Promise<void>
  showReviewActions?: boolean
  showDraftActions?: boolean
  showVersionHistory?: boolean
  showPublishedPricing?: boolean
  canSubmitPublic?: boolean
}) {
  const savePricing = async (payload: { pricingType: "free" | "paid" | "subscription"; priceCents: number }) => {
    if (showPublishedPricing) {
      await marketplaceApi.updateOrgAssetPricing(asset.slug, payload)
    } else {
      await marketplaceApi.updateOrgAsset(asset.slug, payload)
    }
    toast.success("Pricing saved", { description: asset.title })
    await onPricingSaved()
  }

  return (
    <GravitreSurface className="space-y-3 p-4 sm:p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold text-foreground">{asset.title}</h3>
            <Badge variant="outline">{asset.assetType.replace(/_/g, " ")}</Badge>
            {showReviewActions ? <Badge variant="secondary">pending review</Badge> : null}
            {showDraftActions ? <Badge variant="secondary">draft</Badge> : null}
            {showVersionHistory ? <Badge variant="secondary">published</Badge> : null}
            {showPublishedPricing ? <Badge variant="outline">public catalog</Badge> : null}
            <Badge variant="outline">{formatAssetPriceLabel(asset.pricingType, asset.priceCents)}</Badge>
          </div>
          {asset.description ? (
            <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{asset.description}</p>
          ) : null}
          {asset.reviewFeedback ? (
            <p className="mt-2 rounded-md bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
              Review feedback: {asset.reviewFeedback}
            </p>
          ) : null}
          <p className="mt-1 text-xs text-muted-foreground">{asset.slug}</p>
        </div>
        {showReviewActions && onApprove && onReject ? (
          <div className="flex shrink-0 gap-2">
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
        ) : null}
        {showDraftActions && onSubmit && onArchive ? (
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button size="sm" disabled={Boolean(busy)} onClick={() => onSubmit(asset)}>
              {busy === asset.id ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
              ) : (
                <Send className="mr-1.5 h-3.5 w-3.5" aria-hidden />
              )}
              Internal review
            </Button>
            {canSubmitPublic && onSubmitPublic ? (
              <Button size="sm" variant="secondary" disabled={Boolean(busy)} onClick={() => onSubmitPublic(asset)}>
                <Globe className="mr-1.5 h-3.5 w-3.5" aria-hidden />
                Public catalog
              </Button>
            ) : null}
            <Button size="sm" variant="outline" disabled={Boolean(busy)} onClick={() => onArchive(asset)}>
              <Trash2 className="mr-1.5 h-3.5 w-3.5" aria-hidden />
              Archive
            </Button>
          </div>
        ) : null}
      </div>
      {showDraftActions ? (
        <AssetOutcomeEditor
          businessOutcome={asset.businessOutcome}
          useCase={asset.useCase}
          estimatedHoursSaved={asset.estimatedHoursSaved}
          disabled={Boolean(busy)}
          onSave={async (payload) => {
            await marketplaceApi.updateOrgAsset(asset.slug, payload)
            toast.success("Outcome saved", { description: asset.title })
            await onPricingSaved()
          }}
        />
      ) : null}
      {showDraftActions || showReviewActions || showPublishedPricing ? (
        <AssetPricingEditor
          pricingType={asset.pricingType}
          priceCents={asset.priceCents}
          disabled={Boolean(busy)}
          onSave={savePricing}
        />
      ) : null}
      {showVersionHistory ? (
        <AssetVersionHistory slug={asset.slug} disabled={Boolean(busy)} onRolledBack={onPricingSaved} />
      ) : null}
    </GravitreSurface>
  )
}

export default function MarketplaceOrgAdminPage() {
  const { user } = useAuth()
  const { isAdmin } = useOrgAdmin()
  const [busy, setBusy] = useState<string | null>(null)
  const [rejectTarget, setRejectTarget] = useState<MarketplaceAssetSummary | null>(null)
  const [rejectReason, setRejectReason] = useState("")

  const { data: draftData, error: draftError, isLoading: draftsLoading, mutate: mutateDrafts } = useSWR(
    user && isAdmin ? "marketplace-org-admin-drafts" : null,
    () => marketplaceApi.listOrgAssets({ status: "draft", limit: 100 }),
  )

  const { data, error, isLoading, mutate } = useSWR(
    user && isAdmin ? "marketplace-org-admin-queue" : null,
    () => marketplaceApi.listOrgAssets({ status: "pending_review", limit: 100 }),
  )

  const { data: publishedData, isLoading: publishedLoading, mutate: mutatePublished } = useSWR(
    user && isAdmin ? "marketplace-org-admin-published" : null,
    () => marketplaceApi.listOrgAssets({ status: "published", limit: 100 }),
  )

  const { data: publisherData } = useSWR(
    user && isAdmin ? "marketplace-org-admin-publisher" : null,
    () => marketplaceApi.getPublisherProfile(),
  )

  const { data: publicPendingData, mutate: mutatePublicPending } = useSWR(
    user && isAdmin && publisherData?.publisher?.publicPublishingEnabled
      ? "marketplace-org-admin-public-pending"
      : null,
    () => marketplaceApi.listOrgAssets({ status: "pending_review", reviewScope: "public", limit: 100 }),
  )

  const drafts = draftData?.assets ?? []
  const pending = data?.assets ?? []
  const published = (publishedData?.assets ?? []).filter((asset) => asset.visibility === "internal")
  const publicPublished = (publishedData?.assets ?? []).filter((asset) => asset.visibility === "public")
  const publicPending = publicPendingData?.assets ?? []
  const canSubmitPublic = Boolean(publisherData?.publisher?.publicPublishingEnabled)

  const refreshAll = async () => {
    await Promise.all([mutate(), mutateDrafts(), mutatePublished(), mutatePublicPending()])
  }

  const handleApprove = async (asset: MarketplaceAssetSummary) => {
    setBusy(asset.id)
    try {
      await marketplaceApi.approveOrgAsset(asset.slug)
      toast.success(`${asset.title} published internally`)
      await refreshAll()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Approve failed")
    } finally {
      setBusy(null)
    }
  }

  const handleSubmit = async (asset: MarketplaceAssetSummary) => {
    setBusy(asset.id)
    try {
      await marketplaceApi.submitAssetForReview(asset.slug)
      toast.success(`${asset.title} submitted for internal review`)
      await refreshAll()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Submit failed")
    } finally {
      setBusy(null)
    }
  }

  const handleSubmitPublic = async (asset: MarketplaceAssetSummary) => {
    setBusy(asset.id)
    try {
      await marketplaceApi.submitAssetForPublicReview(asset.slug)
      toast.success(`${asset.title} submitted to Gravitre public review`)
      await refreshAll()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Public submit failed")
    } finally {
      setBusy(null)
    }
  }

  const handleArchive = async (asset: MarketplaceAssetSummary) => {
    setBusy(asset.id)
    try {
      await marketplaceApi.archiveOrgAsset(asset.slug)
      toast.success(`${asset.title} archived`)
      await refreshAll()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Archive failed")
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
      await marketplaceApi.rejectOrgAsset(rejectTarget.slug, reason)
      toast.success("Returned to draft")
      setRejectTarget(null)
      setRejectReason("")
      await refreshAll()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Reject failed")
    } finally {
      setBusy(null)
    }
  }

  if (!isAdmin) {
    return (
      <AppShell title="Org marketplace admin">
        <div className="bg-[color:var(--g-canvas)] px-[var(--np-page-pad-sm)] py-6 sm:px-[var(--np-page-pad)]">
          <GravitreSurface className="mx-auto max-w-lg text-center text-sm text-muted-foreground">
            Admin access is required to review org-published assets.
          </GravitreSurface>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title="Internal publish queue">
      <div className="bg-[color:var(--g-canvas)]">
        <GravitrePageHeader
          eyebrow="Gravitre Marketplace"
          title="Org marketplace admin"
          description="Create drafts, publish internally, or submit to the public catalog after publisher onboarding."
          icon={<Shield className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" asChild>
                <Link href="/marketplace/assets">
                  <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
                  Marketplace
                </Link>
              </Button>
              {!canSubmitPublic ? (
                <Button size="sm" variant="outline" asChild>
                  <Link href="/marketplace/publisher">Become a publisher</Link>
                </Button>
              ) : null}
              <Button size="sm" asChild>
                <Link href="/marketplace/org/assets/new">
                  <PlusCircle className="mr-1.5 h-4 w-4" aria-hidden />
                  New draft
                </Link>
              </Button>
            </div>
          }
        />

        <div className="mx-auto max-w-3xl space-y-8 px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)] sm:py-5">
          <section className="grid grid-cols-2 gap-[var(--np-kpi-gap)] sm:grid-cols-4">
            <GravitreMetric
              label="Drafts"
              value={draftsLoading && !draftData ? "—" : drafts.length}
            />
            <GravitreMetric
              label="Internal queue"
              value={isLoading && !data ? "—" : pending.length}
            />
            <GravitreMetric
              label="Published internal"
              value={publishedLoading && !publishedData ? "—" : published.length}
            />
            <GravitreMetric
              label="Public pending"
              value={canSubmitPublic ? publicPending.length : "—"}
              hint={canSubmitPublic ? "Gravitre review" : "Publisher required"}
            />
          </section>

          {canSubmitPublic ? (
            <GravitreSurface className="border-primary/20 bg-primary/5 text-sm text-muted-foreground">
              Public publishing is enabled for{" "}
              <span className="font-medium text-foreground">
                {publisherData?.publisher?.displayName}
              </span>
              . Use <strong className="font-medium text-foreground">Public catalog</strong> on drafts to
              reach the Gravitre review queue.
            </GravitreSurface>
          ) : null}

          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-foreground">Draft assets</h2>
            {draftsLoading && !draftData ? (
              <div className="h-24 animate-pulse rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-2)]" />
            ) : draftError ? (
              <GravitreSurface className="border-destructive/30 bg-destructive/5 text-sm text-destructive">
                Could not load draft assets.
              </GravitreSurface>
            ) : drafts.length === 0 ? (
              <GravitreEmpty
                title="No draft assets yet"
                hint="Create a draft to start the internal publish flow."
                action={
                  <Button size="sm" asChild>
                    <Link href="/marketplace/org/assets/new">Create one</Link>
                  </Button>
                }
              />
            ) : (
              drafts.map((asset) => (
                <OrgAssetRow
                  key={asset.id}
                  asset={asset}
                  busy={busy}
                  showDraftActions
                  canSubmitPublic={canSubmitPublic}
                  onSubmit={handleSubmit}
                  onSubmitPublic={handleSubmitPublic}
                  onArchive={handleArchive}
                  onPricingSaved={refreshAll}
                />
              ))
            )}
          </section>

          {canSubmitPublic ? (
            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-foreground">Public catalog submissions</h2>
              {publicPending.length === 0 ? (
                <GravitreEmpty
                  title="No drafts awaiting Gravitre public review"
                  hint="Submit a draft with Public catalog to reach the platform queue."
                />
              ) : (
                publicPending.map((asset) => (
                  <GravitreSurface
                    key={asset.id}
                    className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-4"
                  >
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-semibold">{asset.title}</h3>
                        <Badge variant="secondary">public review</Badge>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">{asset.slug}</p>
                    </div>
                    <Button size="sm" variant="outline" asChild>
                      <Link href="/marketplace/platform-admin">View platform queue</Link>
                    </Button>
                  </GravitreSurface>
                ))
              )}
            </section>
          ) : null}

          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-foreground">Internal publish queue</h2>
            {isLoading && !data ? (
              <div className="h-24 animate-pulse rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-2)]" />
            ) : error ? (
              <GravitreSurface className="border-destructive/30 bg-destructive/5 text-sm text-destructive">
                Could not load pending assets.
              </GravitreSurface>
            ) : pending.length === 0 ? (
              <GravitreEmpty title="No assets awaiting review" hint="Submitted drafts appear here for approval." />
            ) : (
              pending.map((asset) => (
                <OrgAssetRow
                  key={asset.id}
                  asset={asset}
                  busy={busy}
                  showReviewActions
                  onApprove={handleApprove}
                  onReject={setRejectTarget}
                  onPricingSaved={refreshAll}
                />
              ))
            )}
          </section>

          {canSubmitPublic && publicPublished.length > 0 ? (
            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-foreground">Published public catalog assets</h2>
              <p className="text-xs text-muted-foreground">
                Update pricing on live public assets without unpublishing.
              </p>
              {publicPublished.map((asset) => (
                <OrgAssetRow
                  key={asset.id}
                  asset={asset}
                  busy={busy}
                  showPublishedPricing
                  onPricingSaved={refreshAll}
                />
              ))}
            </section>
          ) : null}

          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-foreground">Published internal assets</h2>
            {publishedLoading && !publishedData ? (
              <div className="h-24 animate-pulse rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-2)]" />
            ) : published.length === 0 ? (
              <GravitreEmpty
                title="No published internal assets yet"
                hint="Approved assets appear here with version history and rollback."
              />
            ) : (
              published.map((asset) => (
                <OrgAssetRow
                  key={asset.id}
                  asset={asset}
                  busy={busy}
                  showVersionHistory
                  onPricingSaved={refreshAll}
                />
              ))
            )}
          </section>
        </div>
      </div>

      <Dialog open={Boolean(rejectTarget)} onOpenChange={(open) => !open && setRejectTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject {rejectTarget?.title}</DialogTitle>
            <DialogDescription>
              The author will see this feedback and can revise the draft before resubmitting.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={rejectReason}
            onChange={(event) => setRejectReason(event.target.value)}
            placeholder="What needs to change before this can be published?"
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
