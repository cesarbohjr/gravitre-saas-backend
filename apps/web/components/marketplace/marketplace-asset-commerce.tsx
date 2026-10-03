"use client"

import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { CheckCircle2, ChevronDown } from "lucide-react"
import { ProviderLogo } from "@/components/gravitre/provider-logo"
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
      <p className="mb-1 text-xs font-semibold text-muted-foreground">{title}</p>
      {description ? <p className="mb-2 text-[11px] text-muted-foreground">{description}</p> : null}
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.connectorType} className="space-y-1 text-sm">
            <div className="flex items-start justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2">
                <ProviderLogo provider={item.connectorType} label={item.label} size="sm" decorative className="shrink-0" />
                {item.connected ? (
                  <CheckCircle2 className={cn("h-3.5 w-3.5 shrink-0", checklistTone(item))} aria-label="Connected" />
                ) : null}
                <span className={cn("min-w-0 break-words", !item.connected && item.required && "font-medium")}>
                  {item.label || item.connectorType}
                  {item.required ? (
                    <span className={cn("ml-1 text-xs font-semibold", !item.connected && "text-destructive")}>Required</span>
                  ) : (
                    <span className="ml-1 text-[10px] text-muted-foreground">Optional</span>
                  )}
                </span>
              </div>
              {!item.connected ? (
                <Button size="sm" variant="outline" className="min-h-11 shrink-0 sm:min-h-8" asChild>
                  <Link href={item.action_url || item.connectPath} aria-label={`Connect ${item.label || item.connectorType}`}>Connect</Link>
                </Button>
              ) : null}
            </div>
            {item.requirementNote ? (
              <p className="pl-6 text-[11px] text-muted-foreground text-pretty">{item.requirementNote}</p>
            ) : null}
            {item.discoveryLimitation || item.warning ? (
              <p
                className="pl-6 text-[11px] text-pretty text-[color:var(--status-pending)]"
                data-testid="apollo-discovery-limitation"
              >
                {item.discoveryLimitation || item.warning}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}

function packItemTypeLabel(item: MarketplacePackItem): string {
  return (item.child.assetType || "item").replace(/_/g, " ")
}

function groupPackItems(items: MarketplacePackItem[]): { type: string; items: MarketplacePackItem[] }[] {
  const groups = new Map<string, MarketplacePackItem[]>()
  for (const item of items) {
    const type = packItemTypeLabel(item)
    const current = groups.get(type) ?? []
    current.push(item)
    groups.set(type, current)
  }
  return [...groups.entries()].map(([type, grouped]) => ({ type, items: grouped }))
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

  const groups = groupPackItems(items)
  const body = (
    <div className={cn("space-y-3", compact ? "text-xs" : "text-sm")}>
      {groups.map((group) => (
        <div key={group.type}>
          <p className={cn(TYPE.eyebrow, "mb-1.5 capitalize")}>
            {group.type}
            <span className="ml-1 tabular-nums">({group.items.length})</span>
          </p>
          <ul className="space-y-1.5">
            {group.items.map((item) => (
              <li key={item.child.id} className="flex items-start justify-between gap-3">
                {linkChildren && item.child.slug ? (
                  <Link href={`/marketplace/assets/${encodeURIComponent(item.child.slug)}`} className="min-w-0 flex-1 break-words rounded-sm text-[color:var(--g-emerald-deep)] underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[color:var(--g-brand)]">
                    {item.child.title}
                  </Link>
                ) : (
                  <span className="min-w-0 flex-1 break-words text-foreground">{item.child.title}</span>
                )}
                <span className="shrink-0 text-xs text-muted-foreground">{item.required ? "Required" : "Optional"}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )

  if (compact) {
    return (
      <details className="group rounded-[10px] border border-divide bg-[color:var(--g-surface-1)] px-3">
        <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 rounded-sm text-xs font-semibold text-muted-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--g-brand)] [&::-webkit-details-marker]:hidden">
          <span>What&apos;s included ({items.length})</span>
          <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" aria-hidden />
        </summary>
        <div className="pb-3">{body}</div>
      </details>
    )
  }

  return (
    <section aria-label="Pack contents" className="rounded-[10px] border border-divide bg-[color:var(--g-surface-1)] p-4">
      <p className="mb-2 text-xs font-semibold text-muted-foreground">
        What&apos;s included ({items.length})
      </p>
      {body}
    </section>
  )
}

export function NonAdminPurchaseNotice() {
  return (
    <p className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
      Ask your org admin or owner to purchase and install this asset into your workspace.
    </p>
  )
}
