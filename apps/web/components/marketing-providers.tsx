"use client"

import type { ReactNode } from "react"
import { ThemeProvider } from "@/components/theme-provider"
import { MotionProvider } from "@/components/motion-provider"
import { AuthProvider } from "@/lib/auth-context"

/**
 * Minimal provider tree for anonymous marketing routes — skips the operator
 * app shell (AI workspace, entitlements, onboarding, etc.) so Lighthouse /
 * crawlers do not download and hydrate that JS on / and /pricing.
 */
export function MarketingProviders({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      forcedTheme="light"
      enableSystem={false}
      disableTransitionOnChange
    >
      <MotionProvider>
        <AuthProvider>{children}</AuthProvider>
      </MotionProvider>
    </ThemeProvider>
  )
}
