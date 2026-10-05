"use client"

import Link from "next/link"
import { CheckCircle2, Plug, AlertTriangle } from "lucide-react"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { ConnectorChecklist, PackContentsPreview, assetRequiresPurchase } from "@/components/marketplace/marketplace-asset-commerce"
import type { MarketplaceAssetSummary } from "@/types/api"

export function PackPreviewSheet({
  asset,
  open,
  onOpenChange,
}: {
  asset: MarketplaceAssetSummary | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  if (!asset) return null

  const detailHref = `/marketplace/assets/${encodeURIComponent(asset.slug)}`

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto bg-[color:var(--g-canvas)] sm:max-w-lg">
        <SheetHeader>
          <p className="text-xs font-semibold text-[color:var(--g-emerald-deep)]">Explore / {asset.department || "Pack preview"}</p>
          <SheetTitle className="pr-5 font-sans text-2xl font-medium">{asset.title}</SheetTitle>
          <SheetDescription>{asset.description}</SheetDescription>
        </SheetHeader>

        <div className="space-y-4 px-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
          {asset.businessOutcome ? <p className="rounded-[10px] bg-[color:var(--g-emerald-pale)] p-4 text-sm leading-6 text-[color:var(--g-carbon)]">{asset.businessOutcome}</p> : null}
          {asset.installed ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2.5 py-1 text-xs font-medium text-success">
              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
              Installed
            </span>
          ) : asset.canInstall && !assetRequiresPurchase(asset) ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
              <Plug className="h-3.5 w-3.5" aria-hidden />
              Ready to install
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning">
              <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
              {assetRequiresPurchase(asset) ? "Purchase required" : asset.connectorsReady ? "Review install requirements" : `${asset.requiredConnectorsConnected}/${asset.requiredConnectorsTotal} required apps connected`}
            </span>
          )}

          {asset.packItems?.length ? (
            <div>
              <p className="mb-2 text-sm font-medium text-foreground">Included in this pack</p>
              <PackContentsPreview items={asset.packItems} compact linkChildren />
            </div>
          ) : null}

          {asset.connectorChecklist?.length ? (
            <div className="rounded-[10px] bg-[color:var(--g-surface-1)] p-4"><ConnectorChecklist items={asset.connectorChecklist} /></div>
          ) : null}

          <div className="flex flex-wrap gap-2 pt-2">
            <Button asChild className="min-h-11">
              <Link href={detailHref}>{asset.installed ? "Manage pack" : "View pack"}</Link>
            </Button>
            <Button variant="outline" className="min-h-11" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
