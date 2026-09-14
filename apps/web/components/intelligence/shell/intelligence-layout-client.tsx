"use client"

import { IntelligenceExperienceProvider } from "@/components/intelligence/shell/intelligence-experience-provider"
import type { ReactNode } from "react"

export function IntelligenceLayoutClient({ children }: { children: ReactNode }) {
  return <IntelligenceExperienceProvider>{children}</IntelligenceExperienceProvider>
}
