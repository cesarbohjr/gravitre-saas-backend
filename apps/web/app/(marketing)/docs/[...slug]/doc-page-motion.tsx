"use client"

import { GravitreReveal } from "@/components/marketing/system"

export function DocPageMotion({ children }: { children: React.ReactNode }) {
  return (
    <GravitreReveal kind="focus">
      {children}
    </GravitreReveal>
  )
}
