"use client"

import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { CheckCircle2, ChevronDown, Plug } from "lucide-react"
import type {
  MarketplaceAssetSummary,
  MarketplaceConnectorChecklistItem,
  MarketplacePackItem,
} from "@/types/api"

export function isFreeAsset(asset: Pick<MarketplaceAssetSummary, "pricingType" | "priceCents">): boolean {
  return asset.pricingType === "free" || !asset.priceCents
}

export function assetRequiresPurchase(asset: MarketplaceAssetSummary): boolean {
  if (asset.installed) return false
  if (asset.hasEntitlement) return false
  if (asset.requiresPayment === true) return true
  if (asset.requiresPayment === false) return false
  return !isFreeAsset(asset)
}

export function formatAssetPrice(asset: Pick<MarketplaceAssetSummary, "pricingType" | "priceCents">): string {
  const cents = asset.priceCents ?? 0
  const amount = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: cents % 100 === 0 ? 0 : 2,
  }).format(cents / 100)
  if (asset.pricingType === "flat_monthly") return `${amount}/mo`
  if (asset.pricingType === "per_invocation") return `${amount}/run`
  if (asset.pricingType === "subscription") return `${amount}/mo`
  return amount
}

export function PriceBadge({ asset, className }: { asset: MarketplaceAssetSummary; className?: string }) {
  if (isFreeAsset(asset)) {
    return (
      <Badge variant="secondary" className={cn("font-medium", className)}>
        Free
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className={cn("border-primary/30 bg-primary/5 font-semibold text-primary", className)}>
      {formatAssetPrice(asset)}
    </Badge>
  )
}

export function EntitlementBadge({ asset }: { asset: MarketplaceAssetSummary }) {
  if (asset.installed) {
    return (
      <Badge variant="secondary" className="bg-success/10 text-success">
        Installed
      </Badge>
    )
  }
  if (asset.hasEntitlement && asset.requiresPayment) {
    return (
      <Badge variant="secondary" className="bg-primary/10 text-primary">
        Purchased
      </Badge>
    )
  }
  if (assetRequiresPurchase(asset)) {
    return (
      <Badge variant="outline" className="border-warning/40 bg-warning/10 text-warning">
        Purchase required
      </Badge>
    )
  }
  return null
}

function checklistTone(item: MarketplaceConnectorChecklistItem) {
  if (item.connected) return "text-success"
  if (item.required) return "text-destructive"
  return "text-muted-foreground"
}

export function ConnectorChecklist({
  items,
  title = "Apps to connect",
  description = "Required apps block install until connected. Optional apps unlock more automation.",
}: {
  items: MarketplaceConnectorChecklistItem[]
  title?: string
  description?: string
}) {
  if (!items.length) return null
  return (
    <div>
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{title}</p>
      {description ? <p className="mb-2 text-[11px] text-muted-foreground">{description}</p> : null}
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.connectorType} className="flex items-start justify-between gap-2 text-sm">
            <div className="flex min-w-0 items-center gap-2">
              {item.connected ? (
                <CheckCircle2 className={cn("h-4 w-4 shrink-0", checklistTone(item))} aria-hidden />
              ) : (
                <Plug className={cn("h-4 w-4 shrink-0", checklistTone(item))} aria-hidden />
              )}
              <span className={cn("truncate", !item.connected && item.required && "font-medium")}>
                {item.label || item.connectorType}
                {item.required ? (
                  <span className="ml-1 text-[10px] font-semibold uppercase text-destructive">Required</span>
                ) : (
                  <span className="ml-1 text-[10px] text-muted-foreground">Optional</span>
                )}
              </span>
            </div>
            {!item.connected ? (
              <Button size="sm" variant="outline" className="shrink-0" asChild>
                <Link href={item.action_url || item.connectPath}>Connect</Link>
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function PackContentsPreview({
  items,
  compact = false,
  linkChildren = false,
}: {
  items: MarketplacePackItem[] | undefined
  compact?: boolean
  linkChildren?: boolean
}) {
  if (!items?.length) return null

  const body = (
    <ul className={cn("space-y-1.5", compact ? "text-xs" : "text-sm")}>
      {items.map((item) => (
        <li key={item.child.id} className="flex items-center justify-between gap-2">
          {linkChildren && item.child.slug ? (
            <Link href={`/marketplace/assets/${encodeURIComponent(item.child.slug)}`} className="text-primary hover:underline">
              {item.child.title}
            </Link>
          ) : (
            <span className="text-foreground">{item.child.title}</span>
          )}
          <Badge variant="outline" className="text-[10px] capitalize">
            {(item.child.assetType || "item").replace(/_/g, " ")}
          </Badge>
        </li>
      ))}
    </ul>
  )

  if (compact) {
    return (
      <details className="group mb-4 rounded-lg border border-border/60 bg-muted/20 p-3">
        <summary className="flex cursor-pointer list-none items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-muted-foreground [&::-webkit-details-marker]:hidden">
          <span>What&apos;s included ({items.length})</span>
          <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" aria-hidden />
        </summary>
        <div className="mt-3">{body}</div>
      </details>
    )
  }

  return (
    <div className="rounded-lg border bg-muted/20 p-4">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        What&apos;s included ({items.length})
      </p>
      {body}
    </div>
  )
}

export function NonAdminPurchaseNotice() {
  return (
    <p className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
      Ask your org admin or owner to purchase and install this asset into your workspace.
    </p>
  )
}
