import { marketingMetadata } from "@/lib/seo"
import { FeaturesSectionPage } from "@/components/marketing/features/features-section-page"

export const metadata = marketingMetadata({
  title: "Meson | Features",
  description:
    "One prompt builds agents, training data, and workflow drafts — configured for your review before production.",
})

export default function FeaturesMesonPage() {
  return <FeaturesSectionPage section="meson" />
}
