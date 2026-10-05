"use client"

import { ArrowRight, BookOpen, Bot, Package, Workflow } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { MarketplaceAssetSummary } from "@/types/api"

/** Figma 8:23 + 8:32 composition, populated exclusively by the visible catalog. */
export function MarketplaceFeaturedOutcome({
  asset,
  onPreview,
}: {
  asset: MarketplaceAssetSummary
  onPreview: (asset: MarketplaceAssetSummary) => void
}) {
  const contents = asset.packItems ?? []
  return (
    <section aria-labelledby="marketplace-featured-title" className="grid overflow-hidden rounded-xl md:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]" data-testid="marketplace-featured-outcome">
      <div className="flex min-w-0 flex-col items-start bg-[color:var(--g-emerald-deep)] p-5 text-white sm:p-6">
        <p className="text-xs font-semibold text-[color:var(--g-emerald-mint)]">Explore / {asset.department || "Outcome pack"}</p>
        <h2 id="marketplace-featured-title" className="mt-3 font-[family-name:var(--font-space-grotesk)] text-[21px] sm:text-[27px] font-medium leading-tight text-balance">{asset.title}</h2>
        {asset.businessOutcome || asset.description ? (
          <p className="mt-3 max-w-xl text-sm leading-relaxed text-[color:var(--g-emerald-mint)]">{asset.businessOutcome || asset.description}</p>
        ) : null}
        <Button onClick={() => onPreview(asset)} className="mt-5 min-h-11 bg-white text-[color:var(--g-emerald-deep)] hover:bg-[color:var(--g-emerald-mint)] focus-visible:ring-white">
          Explore pack <ArrowRight className="ml-2 size-4" aria-hidden />
        </Button>
      </div>
      <div className="hidden min-w-0 bg-[color:var(--g-carbon)] p-6 text-[color:var(--g-emerald-mint)] md:block">
        <h3 className="text-xs font-semibold text-white/65">Pack composition</h3>
        {contents.length > 0 ? (
          <ul className="mt-4 space-y-3">
            {contents.slice(0, 3).map(({ child }) => {
              const Icon = child.assetType === "ai_agent" ? Bot : child.assetType === "workflow" || child.assetType === "play" ? Workflow : child.assetType === "knowledge_pack" ? BookOpen : Package
              return <li key={child.id} className="flex items-start gap-3 text-sm leading-5"><Icon className="mt-0.5 size-4 shrink-0" aria-hidden /><span>{child.title}</span></li>
            })}
          </ul>
        ) : <p className="mt-4 text-sm text-white/75">Open the pack to inspect its setup.</p>}
        <p className="mt-5 border-t border-white/10 pt-3 text-xs text-white/65">
          {contents.length > 0 ? `${contents.length} included ${contents.length === 1 ? "component" : "components"} · ` : ""}
          {asset.connectorChecklist.length} {asset.connectorChecklist.length === 1 ? "connector" : "connectors"}
        </p>
      </div>
    </section>
  )
}
