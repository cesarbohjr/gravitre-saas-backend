import { marketingMetadata } from "@/lib/seo"
import { FeaturesSectionPage } from "@/components/marketing/features/features-section-page"

export const metadata = marketingMetadata({
  title: "Governance | Features",
  description:
    "Human-in-the-loop approval, audit trails, RBAC, and org-scoped LLM routing — built into execution.",
})

export default function FeaturesGovernancePage() {
  return <FeaturesSectionPage section="governance" />
}
