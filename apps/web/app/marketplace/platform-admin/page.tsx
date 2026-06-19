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
import { fetcher } from "@/lib/fetcher"
import { ArrowLeft, CheckCircle2, Globe, Loader2, XCircle } from "lucide-react"
import { toast } from "sonner"
import type { MarketplaceAssetSummary } from "@/types/api"

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
  return (
    <div className="space-y-3 rounded-xl border border-border bg-card p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold">{asset.title}</h3>
            <Badge variant="secondary">public review</Badge>
          </div>
          {asset.description ? (
            <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{asset.description}</p>
          ) : null}
          <p className="mt-1 text-xs text-muted-foreground">{asset.slug}</p>
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

  const { data, error, isLoading, mutate } = useSWR(
    user && isPlatformAdmin ? "marketplace-platform-queue" : null,
    () => marketplaceApi.listPlatformReviewQueue({ limit: 100 }),
  )

  const pending = data?.assets ?? []

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
