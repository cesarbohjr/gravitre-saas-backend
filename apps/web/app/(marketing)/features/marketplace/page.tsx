import { marketingMetadata } from "@/lib/seo"
import { MarketplacePage } from "@/components/marketing/features/marketplace-page"

export const metadata = marketingMetadata({
  canonical: "/features/marketplace",
  title: "AI Plays and Workflow Marketplace",
  description:
    "60+ installable workflow templates, department packs, agents, and knowledge — connector readiness checks before install, human approval on writes.",
})

export default function FeaturesMarketplacePage() {
  return <MarketplacePage />
}
