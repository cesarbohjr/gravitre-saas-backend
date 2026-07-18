import { marketingMetadata } from "@/lib/seo"
import { FeaturesSectionPage } from "@/components/marketing/features/features-section-page"

export const metadata = marketingMetadata({
  title: "Agents | Features",
  description:
    "Department agents with profiles, health scores, and verified outcomes — not chat personas alone.",
})

export default function FeaturesAgentsPage() {
  return <FeaturesSectionPage section="agents" />
}
