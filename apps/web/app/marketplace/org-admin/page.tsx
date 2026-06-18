"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
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

function PendingAssetRow({
  asset,
  busy,
  onApprove,
  onReject,
}: {
  asset: MarketplaceAssetSummary
  busy: string | null
  onApprove: (asset: MarketplaceAssetSummary) => void
  onReject: (asset: MarketplaceAssetSummary) => void
}) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-semibold text-foreground">{asset.title}</h3>
          <Badge variant="outline">{asset.assetType.replace(/_/g, " ")}</Badge>
          <Badge variant="secondary">pending review</Badge>
        </div>
        {asset.description ? (
          <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{asset.description}</p>
        ) : null}
        <p className="mt-1 text-xs text-muted-foreground">{asset.slug}</p>
      </div>
      <div className="flex shrink-0 gap-2">
        <Button
          size="sm"
          disabled={Boolean(busy)}
          onClick={() => onApprove(asset)}
        >
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
  )
}

export default function MarketplaceOrgAdminPage() {
  const { user } = useAuth()
  const role = user?.role
  const isAdmin = role === "admin" || role === "owner"
  const [busy, setBusy] = useState<string | null>(null)
  const [rejectTarget, setRejectTarget] = useState<MarketplaceAssetSummary | null>(null)
  const [rejectReason, setRejectReason] = useState("")

  const { data, error, isLoading, mutate } = useSWR(
    user && isAdmin ? "marketplace-org-admin-queue" : null,
    () => marketplaceApi.listOrgAssets({ status: "pending_review", limit: 100 }),
  )

  const pending = data?.assets ?? []

  const handleApprove = async (asset: MarketplaceAssetSummary) => {
    setBusy(asset.id)
    try {
      await marketplaceApi.approveOrgAsset(asset.slug)
      toast.success(`${asset.title} published internally`)
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
      await marketplaceApi.rejectOrgAsset(rejectTarget.slug, reason)
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
      <div className="mx-auto max-w-3xl space-y-6">
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link href="/marketplace">
            <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
            Marketplace
          </Link>
        </Button>

        <header>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <Shield className="h-5 w-5 text-primary" aria-hidden />
            Internal publish queue
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Review org-owned assets before they appear in your organization&apos;s internal catalog.
          </p>
        </header>

        {isLoading && !data ? (
          <div className="h-32 animate-pulse rounded-xl border bg-muted/40" />
        ) : error ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            Could not load pending assets.
          </div>
        ) : pending.length === 0 ? (
          <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
            No assets awaiting review.
          </div>
        ) : (
          <div className="space-y-3">
            {pending.map((asset) => (
              <PendingAssetRow
                key={asset.id}
                asset={asset}
                busy={busy}
                onApprove={handleApprove}
                onReject={setRejectTarget}
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
