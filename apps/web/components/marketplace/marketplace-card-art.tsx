import { cn } from "@/lib/utils"
import { resolveMarketArt, type MarketArtInput } from "@/lib/marketplace-category-art"

/**
 * Objects-only category art at the top of a marketplace card (300x190 scene).
 * The frame is a fixed 2:1 crop of the scene (sky and margin trimmed, ground line kept), so every card in a grid row starts its
 * copy at the same height, whatever the column width.
 */
export function MarketplaceCardArt({
  asset,
  className,
}: {
  asset: MarketArtInput
  className?: string
}) {
  const art = resolveMarketArt(asset)
  return (
    <div
      className={cn(
        "relative aspect-[2/1] w-full shrink-0 overflow-hidden border-b border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-2)]",
        className,
      )}
      data-market-art={art.name}
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- static decorative SVG */}
      <img
        src={art.src}
        alt=""
        aria-hidden
        loading="lazy"
        decoding="async"
        width={300}
        height={190}
        data-illustration={art.name}
        className="absolute inset-0 block h-full w-full object-cover dark:opacity-90"
      />
    </div>
  )
}
