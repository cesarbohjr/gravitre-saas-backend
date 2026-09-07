import { FeaturesLegacyContent } from "@/components/marketing/features/legacy-page"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { MarketingPageHero, MarketingPageEndCta } from "@/components/marketing/nodus/page-shell"

// The full, single-page Features experience (no side menu). GIBE, Governance,
// and the Marketplace now live on their own top-nav tabs (/features/technology
// and /features/marketplace), so they are excluded here to avoid duplication.
// Metrics & use cases (the "insights" section) stay on this page.
export default function FeaturesPage() {
  return (
    <div className="bg-white">
      <MarketingPageHero
        badge={MARKETING_COPY.featuresHero.badge}
        title={MARKETING_COPY.featuresHero.headline.join(" ")}
        description={MARKETING_COPY.featuresHero.subtitle}
      >
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          {MARKETING_COPY.featuresHero.pills.map((pill) => (
            <span
              key={pill}
              className="px-4 py-2 rounded-full bg-gray-50 border border-divide text-sm font-medium text-charcoal-700"
            >
              {pill}
            </span>
          ))}
        </div>
      </MarketingPageHero>

      <FeaturesLegacyContent 
        showHero={false} 
        showTail={false}
        exclude={["intelligence", "governance", "marketplace"]} 
      />

      <MarketingPageEndCta />
    </div>
  )
}
