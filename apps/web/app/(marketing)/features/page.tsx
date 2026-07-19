import { FeaturesLegacyContent } from "@/components/marketing/features/legacy-page"

// The full, single-page Features experience (no side menu). GIBE, Governance,
// and the Marketplace now live on their own top-nav tabs (/features/technology
// and /features/marketplace), so they are excluded here to avoid duplication.
// Metrics & use cases (the "insights" section) stay on this page.
export default function FeaturesPage() {
  return <FeaturesLegacyContent exclude={["intelligence", "governance", "marketplace"]} />
}
