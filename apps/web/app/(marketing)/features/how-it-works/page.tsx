import { marketingMetadata } from "@/lib/seo"
import { FeaturesSectionPage } from "@/components/marketing/features/features-section-page"

export const metadata = marketingMetadata({
  title: "How It Works | Features",
  description:
    "Your team → Gravitre AI → agents → connected tools. Approval gates and honest metrics at every step.",
})

export default function FeaturesHowItWorksPage() {
  return <FeaturesSectionPage section="how-it-works" />
}
