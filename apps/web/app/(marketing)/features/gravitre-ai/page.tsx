import { marketingMetadata } from "@/lib/seo"
import { FeaturesSectionPage } from "@/components/marketing/features/features-section-page"

export const metadata = marketingMetadata({
  title: "Gravitre AI | Features",
  description:
    "Execute, chat, and search with live connector checks — MCP-native routing with confidence scores.",
})

export default function FeaturesGravitreAiPage() {
  return <FeaturesSectionPage section="gravitre-ai" />
}
