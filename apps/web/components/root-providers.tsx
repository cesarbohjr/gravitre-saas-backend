import { headers } from "next/headers"
import type { ReactNode } from "react"
import { AppProviders } from "@/components/app-providers"
import { MarketingProviders } from "@/components/marketing-providers"

/**
 * Picks marketing vs operator provider trees using `x-gravitre-marketing`
 * set in proxy.ts — SSR-safe, no pathname hydration mismatch.
 */
export async function RootProviders({ children }: { children: ReactNode }) {
  const headerStore = await headers()
  const isMarketing = headerStore.get("x-gravitre-marketing") === "1"

  if (isMarketing) {
    return <MarketingProviders>{children}</MarketingProviders>
  }

  return <AppProviders>{children}</AppProviders>
}
