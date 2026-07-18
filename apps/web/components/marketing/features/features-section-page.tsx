"use client"

import { FeaturesLegacyContent } from "@/components/marketing/features/legacy-page"
import { FeaturesSubHero } from "@/components/marketing/features/features-shell"
import type { FeaturesSectionId } from "@/lib/features-nav"

export function FeaturesSectionPage({ section }: { section: FeaturesSectionId }) {
  return (
    <>
      <FeaturesSubHero sectionId={section} />
      <FeaturesLegacyContent section={section} showHero={false} />
    </>
  )
}
