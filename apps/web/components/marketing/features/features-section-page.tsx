"use client"

import { FeaturesLegacyContent } from "@/components/marketing/features/legacy-page"
import { FeaturesSubHero } from "@/components/marketing/features/features-shell"
import {
  FeatureEnrichment,
  FeatureSectionCTA,
} from "@/components/marketing/features/section-enrichment"
import { getSectionContent } from "@/lib/features-sections-content"
import { FEATURES_NAV, type FeaturesSectionId } from "@/lib/features-nav"

const CTA_LABEL: Partial<Record<FeaturesSectionId, string>> = {
  "gravitre-ai": "Run your operations from one prompt.",
  agents: "Put a verified AI team to work.",
  workflows: "Automate with a safety net.",
  meson: "Go from idea to a working draft.",
  integrations: "Connect your stack and start executing.",
  governance: "Ship AI your security team will approve.",
  marketplace: "Skip the blank canvas.",
  intelligence: "Give your AI a memory and a rulebook.",
  insights: "See exactly what Gravitre measures.",
  "how-it-works": "See Gravitre run end to end.",
}

export function FeaturesSectionPage({ section }: { section: FeaturesSectionId }) {
  const hasEnrichment = Boolean(getSectionContent(section))
  const ctaLabel =
    CTA_LABEL[section] ??
    `Ready to explore ${FEATURES_NAV.find((i) => i.id === section)?.label ?? "Gravitre"}?`

  return (
    <>
      <FeaturesSubHero sectionId={section} />
      <FeaturesLegacyContent section={section} showHero={false} showTail={false} />
      {hasEnrichment ? <FeatureEnrichment sectionId={section} /> : null}
      <FeatureSectionCTA label={ctaLabel} />
    </>
  )
}
