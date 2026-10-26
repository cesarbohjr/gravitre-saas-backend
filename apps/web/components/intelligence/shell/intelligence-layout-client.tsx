"use client"

import { IntelligenceOverlaysProvider } from "@/components/intelligence/overlays/intelligence-overlays"
import { IntelligenceExperienceProvider } from "@/components/intelligence/shell/intelligence-experience-provider"
import type { ReactNode } from "react"

export function IntelligenceLayoutClient({ children }: { children: ReactNode }) {
  return (
    <IntelligenceExperienceProvider>
      <IntelligenceOverlaysProvider>{children}</IntelligenceOverlaysProvider>
    </IntelligenceExperienceProvider>
  )
}
