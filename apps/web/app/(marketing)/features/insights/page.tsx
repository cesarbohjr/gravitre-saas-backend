import { marketingMetadata } from "@/lib/seo"
import { FeaturesSectionPage } from "@/components/marketing/features/features-section-page"

export const metadata = marketingMetadata({
  title: "Metrics & Use Cases | Features",
  description:
    "Three-tier honest reporting — what happened, what is estimated, and what is not verified yet — plus where teams start.",
})

export default function FeaturesInsightsPage() {
  return <FeaturesSectionPage section="insights" />
}
