import { marketingMetadata } from "@/lib/seo"
import { FeaturesSectionPage } from "@/components/marketing/features/features-section-page"

export const metadata = marketingMetadata({
  title: "Integrations | Features",
  description:
    "50+ connectors when configured — live Configured → Authenticated → Healthy → Executable checks.",
})

export default function FeaturesIntegrationsPage() {
  return <FeaturesSectionPage section="integrations" />
}
