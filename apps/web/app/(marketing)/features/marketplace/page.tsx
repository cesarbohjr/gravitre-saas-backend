import { marketingMetadata } from "@/lib/seo"
import { FeaturesSectionPage } from "@/components/marketing/features/features-section-page"

export const metadata = marketingMetadata({
  title: "Marketplace | Features",
  description:
    "60+ installable workflow templates, department packs, agents, and knowledge — connector checks before install.",
})

export default function FeaturesMarketplacePage() {
  return <FeaturesSectionPage section="marketplace" />
}
