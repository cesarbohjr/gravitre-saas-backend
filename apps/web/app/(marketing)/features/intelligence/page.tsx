import { marketingMetadata } from "@/lib/seo"
import { FeaturesSectionPage } from "@/components/marketing/features/features-section-page"

export const metadata = marketingMetadata({
  title: "GIBE Intelligence | Features",
  description:
    "Gravitre Intelligent Business Engine: four-layer stack, org-scoped memory, ML catalog, routing traces, and data-gate honesty.",
})

export default function FeaturesIntelligencePage() {
  return <FeaturesSectionPage section="intelligence" />
}
