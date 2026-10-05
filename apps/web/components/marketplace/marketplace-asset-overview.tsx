"use client"

import type { ReactNode } from "react"
import { AssetTrustBadges } from "./asset-trust-badges"
import { EntitlementBadge, PriceBadge, formatAssetPrice } from "./marketplace-asset-commerce"
import { ESTIMATED_HOURS_SAVED_MONTHLY } from "@/lib/outcome-labels"
import type { MarketplaceAssetDetail } from "@/types/api"

/** Extends Figma 8:2's outcome/context split to the real pack detail. */
export function MarketplaceAssetOverview({ asset, needsPurchase, isAdmin, actions }: { asset: MarketplaceAssetDetail; needsPurchase: boolean; isAdmin: boolean; actions?: ReactNode }) {
  return (
    <header className="grid overflow-hidden rounded-[10px] lg:grid-cols-[minmax(0,1.5fr)_minmax(260px,1fr)]" data-testid="marketplace-asset-overview">
      <div className="min-w-0 bg-[color:var(--g-emerald-deep)] p-5 text-white sm:p-6">
        <p className="text-xs font-semibold text-[color:var(--g-emerald-mint)]">Explore / {asset.department || asset.assetType.replace(/_/g, " ")}</p>
        <h1 className="mt-3 break-words font-sans text-xl font-medium leading-tight sm:text-2xl">{asset.title}</h1>
        {asset.businessOutcome ? <p className="mt-4 text-base leading-7">{asset.businessOutcome}</p> : null}
        {asset.description ? <p className="mt-3 text-sm leading-6 text-[color:var(--g-emerald-mint)]">{asset.description}</p> : null}
        {asset.useCase ? <dl className="mt-4 text-sm"><dt className="text-xs text-[color:var(--g-emerald-mint)]">Use case</dt><dd className="mt-1">{asset.useCase}</dd></dl> : null}
      </div>
      <div className="min-w-0 bg-[color:var(--g-surface-1)] p-5 sm:p-6">
        <h2 className="text-xs font-semibold text-[color:var(--g-emerald-deep)]">Workspace context</h2>
        <p className="mt-2 text-sm capitalize text-muted-foreground">{asset.assetType.replace(/_/g, " ")}</p>
        <div className="mt-3 flex flex-wrap gap-2"><PriceBadge asset={asset} /><EntitlementBadge asset={asset} /><AssetTrustBadges asset={asset} /></div>
        {needsPurchase && isAdmin ? <p className="mt-3 text-sm text-muted-foreground">Purchase ({formatAssetPrice(asset)}) unlocks install into your workspace.</p> : null}
        <dl className="mt-5 space-y-3 text-sm">
          {asset.packItems?.length ? <div><dt className="text-xs text-muted-foreground">Included components</dt><dd className="mt-1 tabular-nums">{asset.packItems.length}</dd></div> : null}
          {asset.connectorChecklist?.length ? <div><dt className="text-xs text-muted-foreground">Required apps connected</dt><dd className="mt-1 tabular-nums">{asset.requiredConnectorsConnected} / {asset.requiredConnectorsTotal}</dd></div> : null}
          {asset.estimatedHoursSaved != null ? <div><dt className="text-xs text-muted-foreground">{ESTIMATED_HOURS_SAVED_MONTHLY}</dt><dd className="mt-1 tabular-nums">{asset.estimatedHoursSaved}h</dd></div> : null}
        </dl>
        {actions ? <div className="mt-5">{actions}</div> : null}
      </div>
    </header>
  )
}
