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
import { PackContentsPreview } from "@/components/marketplace/marketplace-asset-commerce"
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
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{asset.title}</SheetTitle>
          <SheetDescription>{asset.description}</SheetDescription>
        </SheetHeader>

        <div className="mt-4 space-y-4">
          {asset.installed ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2.5 py-1 text-xs font-medium text-success">
              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
              Installed
            </span>
          ) : asset.connectorsReady ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
              <Plug className="h-3.5 w-3.5" aria-hidden />
              Ready to install
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning">
              <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
              {asset.requiredConnectorsConnected}/{asset.requiredConnectorsTotal} apps connected
            </span>
          )}

          {asset.packItems?.length ? (
            <div>
              <p className="mb-2 text-sm font-medium text-foreground">Included in this pack</p>
              <PackContentsPreview items={asset.packItems} compact />
            </div>
          ) : null}

          {asset.connectorChecklist?.length ? (
            <div>
              <p className="mb-2 text-sm font-medium text-foreground">Required connectors</p>
              <ul className="space-y-1 text-sm text-muted-foreground">
                {asset.connectorChecklist.map((connector) => (
                  <li key={connector.connectorType ?? connector.label}>
                    {connector.label ?? connector.connectorType?.replace(/_/g, " ")}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="flex flex-wrap gap-2 pt-2">
            <Button asChild>
              <Link href={detailHref}>{asset.installed ? "Manage pack" : "Install pack"}</Link>
            </Button>
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
