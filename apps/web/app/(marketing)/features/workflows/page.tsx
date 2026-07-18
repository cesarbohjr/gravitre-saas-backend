import { marketingMetadata } from "@/lib/seo"
import { FeaturesSectionPage } from "@/components/marketing/features/features-section-page"

export const metadata = marketingMetadata({
  title: "Workflows | Features",
  description:
    "Visual workflow builder with branching, human-in-the-loop approvals, simulation, and failure predictions.",
})

export default function FeaturesWorkflowsPage() {
  return <FeaturesSectionPage section="workflows" />
}
