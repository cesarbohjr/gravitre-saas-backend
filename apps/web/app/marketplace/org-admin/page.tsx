"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
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
    <div className="space-y-3 rounded-xl border border-border bg-card p-4">
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
    </div>
  )
}

export default function MarketplaceOrgAdminPage() {
  const { user } = useAuth()
  const role = user?.role
  const isAdmin = role === "admin" || role === "owner"
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
        <div className="mx-auto max-w-lg rounded-lg border bg-card p-6 text-center text-sm text-muted-foreground">
          Admin access is required to review org-published assets.
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title="Internal publish queue">
      <div className="mx-auto max-w-3xl space-y-8">
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link href="/marketplace">
            <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
            Marketplace
          </Link>
        </Button>

        <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-xl font-semibold">
              <Shield className="h-5 w-5 text-primary" aria-hidden />
              Org marketplace admin
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Create drafts, publish internally, or submit to the public catalog after publisher onboarding.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
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
        </header>

        {canSubmitPublic ? (
          <div className="rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-muted-foreground">
            Public publishing is enabled for{" "}
            <span className="font-medium text-foreground">
              {publisherData?.publisher?.displayName}
            </span>
            . Use <strong className="font-medium text-foreground">Public catalog</strong> on drafts to
            reach the Gravitre review queue.
          </div>
        ) : null}

        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-foreground">Draft assets</h2>
          {draftsLoading && !draftData ? (
            <div className="h-24 animate-pulse rounded-xl border bg-muted/40" />
          ) : draftError ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
              Could not load draft assets.
            </div>
          ) : drafts.length === 0 ? (
            <div className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
              No draft assets yet.{" "}
              <Link href="/marketplace/org/assets/new" className="text-primary underline-offset-4 hover:underline">
                Create one
              </Link>
              .
            </div>
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
              <div className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
                No drafts awaiting Gravitre public review. Submit a draft with{" "}
                <span className="font-medium text-foreground">Public catalog</span>.
              </div>
            ) : (
              publicPending.map((asset) => (
                <div
                  key={asset.id}
                  className="flex flex-col gap-2 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between"
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
                </div>
              ))
            )}
          </section>
        ) : null}

        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-foreground">Internal publish queue</h2>
          {isLoading && !data ? (
            <div className="h-24 animate-pulse rounded-xl border bg-muted/40" />
          ) : error ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
              Could not load pending assets.
            </div>
          ) : pending.length === 0 ? (
            <div className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
              No assets awaiting review.
            </div>
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
            <div className="h-24 animate-pulse rounded-xl border bg-muted/40" />
          ) : published.length === 0 ? (
            <div className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
              Approved assets appear here with version history and rollback.
            </div>
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
