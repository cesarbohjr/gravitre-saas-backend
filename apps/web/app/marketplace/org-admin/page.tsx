"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { AssetPricingEditor } from "@/components/marketplace/asset-pricing-editor"
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
import { ArrowLeft, CheckCircle2, Loader2, Shield, XCircle } from "lucide-react"
import { toast } from "sonner"
import type { MarketplaceAssetSummary } from "@/types/api"

function OrgAssetRow({
  asset,
  busy,
  onApprove,
  onReject,
  onPricingSaved,
  showReviewActions,
}: {
  asset: MarketplaceAssetSummary
  busy: string | null
  onApprove?: (asset: MarketplaceAssetSummary) => void
  onReject?: (asset: MarketplaceAssetSummary) => void
  onPricingSaved: () => Promise<void>
  showReviewActions?: boolean
}) {
  return (
    <div className="space-y-3 rounded-xl border border-border bg-card p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold text-foreground">{asset.title}</h3>
            <Badge variant="outline">{asset.assetType.replace(/_/g, " ")}</Badge>
            {showReviewActions ? <Badge variant="secondary">pending review</Badge> : <Badge variant="secondary">draft</Badge>}
          </div>
          {asset.description ? (
            <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{asset.description}</p>
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
      </div>
      <AssetPricingEditor
        pricingType={asset.pricingType}
        priceCents={asset.priceCents}
        disabled={Boolean(busy)}
        onSave={async (payload) => {
          await marketplaceApi.updateOrgAsset(asset.slug, payload)
          toast.success("Pricing saved", { description: asset.title })
          await onPricingSaved()
        }}
      />
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

  const drafts = draftData?.assets ?? []
  const pending = data?.assets ?? []

  const refreshAll = async () => {
    await Promise.all([mutate(), mutateDrafts()])
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

        <header>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <Shield className="h-5 w-5 text-primary" aria-hidden />
            Org marketplace admin
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Set pricing on drafts and review org-owned assets before they appear in your internal catalog.
          </p>
        </header>

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
              No draft assets yet.
            </div>
          ) : (
            drafts.map((asset) => (
              <OrgAssetRow
                key={asset.id}
                asset={asset}
                busy={busy}
                onPricingSaved={refreshAll}
              />
            ))
          )}
        </section>

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
