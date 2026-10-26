"use client"

import Link from "next/link"
import type { MarketplaceAssetSummary } from "@/types/api"
import { formatAssetPrice, isFreeAsset } from "@/components/marketplace/marketplace-asset-commerce"
import { IdentityIcon, ListingBadge, ListingCover } from "@/components/marketplace/identity/listing-identity"
import { LISTING_KINDS, identityDepartmentFor, listingKindFor } from "@/lib/listing-identity"
import { listingMeta } from "@/lib/listing-meta"
import type { ListingReadiness } from "@/lib/listing-readiness"
import { cn } from "@/lib/utils"

export type ListingActionHandlers = {
  onOpenDetail: (asset: MarketplaceAssetSummary) => void
  onInstall: (asset: MarketplaceAssetSummary) => void
  onOpenInstalled: (asset: MarketplaceAssetSummary) => void
}

function VerifiedMark() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" aria-label="Verified" role="img">
      <circle cx="12" cy="12" r="10" fill="#0B8A5C" />
      <path d="M8 12.5l2.6 2.6L16 9.6" fill="none" stroke="#FFFFFF" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

/** "by Gravitre" for first-party listings, the publisher otherwise; nothing when neither is known. */
export function publisherLine(asset: MarketplaceAssetSummary): { name: string; verified: boolean } | null {
  if (asset.publisherDisplayName) return { name: asset.publisherDisplayName, verified: Boolean(asset.publisherVerified) }
  if (asset.federated) return asset.vendor ? { name: asset.vendor, verified: false } : null
  if (!asset.orgId) return { name: "Gravitre", verified: true }
  return { name: "your organization", verified: false }
}

export function priceLabel(asset: MarketplaceAssetSummary): string {
  return isFreeAsset(asset) ? "Free" : formatAssetPrice(asset)
}

export function ReadinessButton({
  asset,
  readiness,
  handlers,
  busy,
}: {
  asset: MarketplaceAssetSummary
  readiness: ListingReadiness
  handlers: ListingActionHandlers
  busy?: boolean
}) {
  const { action } = readiness
  const aria = `${action.label} ${asset.title}`
  switch (action.kind) {
    case "connect":
      return (
        <Link className="mp-btn primary" href={action.href} aria-label={aria}>
          Connect
        </Link>
      )
    case "install":
      return (
        <button type="button" className="mp-btn dark" disabled={busy} aria-label={aria} onClick={() => handlers.onInstall(asset)}>
          {action.label}
        </button>
      )
    case "open":
      return (
        <button type="button" className="mp-btn ghost" aria-label={aria} onClick={() => handlers.onOpenInstalled(asset)}>
          Open
        </button>
      )
    default:
      return (
        <button type="button" className="mp-btn ghost" aria-label={aria} onClick={() => handlers.onOpenDetail(asset)}>
          {action.label}
        </button>
      )
  }
}

function KindChip({ assetType }: { assetType: string }) {
  const kind = listingKindFor(assetType)
  return (
    <span className="mp-chip kind">
      {kind === "agent" ? <IdentityIcon d={LISTING_KINDS.agent.icon} size={12} /> : null}
      {LISTING_KINDS[kind].label}
    </span>
  )
}

function DepartmentChip({ department }: { department: string | null | undefined }) {
  if (!department) return null
  const dept = identityDepartmentFor(department)
  return (
    <span className="mp-chip dept" style={{ color: dept.color }}>
      {dept.label}
    </span>
  )
}

/** Grid card: cover, badge, name and publisher, description, chips, readiness footer. */
export function ListingCard({
  asset,
  readiness,
  handlers,
  busy,
}: {
  asset: MarketplaceAssetSummary
  readiness: ListingReadiness
  handlers: ListingActionHandlers
  busy?: boolean
}) {
  const kind = listingKindFor(asset.assetType)
  const meta = listingMeta(asset)
  const by = publisherLine(asset)
  return (
    <article className="mp-card mp-lift" data-testid="marketplace-pack-row" data-kind={kind}>
      <ListingCover kind={kind} department={asset.department} className="mp-cover">
        <span className="mp-price">{priceLabel(asset)}</span>
      </ListingCover>
      <div className="mp-card-id">
        <ListingBadge kind={kind} department={asset.department} />
        <span className="mp-card-name">
          <h3>
            <button type="button" className="mp-open" onClick={() => handlers.onOpenDetail(asset)}>
              {asset.title}
            </button>
          </h3>
          {by ? (
            <span className="mp-by">
              by {by.name} {by.verified ? <VerifiedMark /> : null}
            </span>
          ) : null}
        </span>
      </div>
      <div className="mp-card-body">
        <p className="mp-desc">{asset.description || "No description yet."}</p>
        <div className="mp-chips">
          <KindChip assetType={asset.assetType} />
          <DepartmentChip department={asset.department} />
          {meta ? <span className="mp-chip meta">{meta}</span> : null}
        </div>
      </div>
      <div className="mp-foot">
        <span className="mp-dot" data-state={readiness.state} aria-hidden />
        <span className="mp-status" title={readiness.detail}>
          {readiness.label}
        </span>
        <ReadinessButton asset={asset} readiness={readiness} handlers={handlers} busy={busy} />
      </div>
    </article>
  )
}

/** List view row: the same facts in one line. */
export function ListingRow({
  asset,
  readiness,
  handlers,
  busy,
}: {
  asset: MarketplaceAssetSummary
  readiness: ListingReadiness
  handlers: ListingActionHandlers
  busy?: boolean
}) {
  const kind = listingKindFor(asset.assetType)
  const meta = listingMeta(asset)
  return (
    <li className="mp-row" data-testid="marketplace-pack-row" data-kind={kind}>
      <ListingBadge kind={kind} department={asset.department} size={40} />
      <div className="mp-row-main">
        <h3>
          <button type="button" className="mp-open" onClick={() => handlers.onOpenDetail(asset)}>
            {asset.title}
          </button>
        </h3>
        <p>{asset.description || "No description yet."}</p>
      </div>
      <div className="mp-chips">
        <KindChip assetType={asset.assetType} />
        <DepartmentChip department={asset.department} />
        {meta ? <span className="mp-chip meta">{meta}</span> : null}
        <span className="mp-chip meta">{priceLabel(asset)}</span>
      </div>
      <div className="mp-row-status">
        <span className="mp-dot" data-state={readiness.state} aria-hidden />
        <span className="mp-status" title={readiness.detail}>
          {readiness.label}
        </span>
      </div>
      <ReadinessButton asset={asset} readiness={readiness} handlers={handlers} busy={busy} />
    </li>
  )
}

/** Featured card: taller cover with why it was picked, then name, facts and one action. */
export function FeaturedListingCard({
  asset,
  reason,
  readiness,
  handlers,
}: {
  asset: MarketplaceAssetSummary
  reason: string
  readiness: ListingReadiness
  handlers: ListingActionHandlers
}) {
  const kind = listingKindFor(asset.assetType)
  const facts = [LISTING_KINDS[kind].label, asset.department ? identityDepartmentFor(asset.department).label : null, listingMeta(asset)]
    .filter(Boolean)
    .join(" · ")
  return (
    <article className={cn("mp-card mp-lift")} data-testid="marketplace-featured">
      <ListingCover kind={kind} department={asset.department} className="mp-cover tall">
        <span className="mp-flag">{reason}</span>
      </ListingCover>
      <div className="mp-featured-body">
        <span className="mp-card-name" style={{ flex: "1 1 0%" }}>
          <strong>
            <button type="button" className="mp-open" onClick={() => handlers.onOpenDetail(asset)}>
              {asset.title}
            </button>
          </strong>
          <small>{facts}</small>
        </span>
        <ReadinessButton asset={asset} readiness={readiness} handlers={handlers} />
      </div>
    </article>
  )
}
