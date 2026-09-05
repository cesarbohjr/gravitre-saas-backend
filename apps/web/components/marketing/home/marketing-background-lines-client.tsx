"use client"

/**
 * Client-only boundary for MarketingBackgroundLines.
 *
 * `next/dynamic(..., { ssr: false })` is not allowed inside a Server
 * Component (see app/(marketing)/page.tsx, which has no "use client").
 * This wrapper is itself a Client Component, so it is the one place
 * allowed to opt the (purely decorative, reduced-motion-sensitive)
 * background lines out of SSR — avoiding a server/client render mismatch
 * from `useMotionPrefs()` without breaking the marketing page build.
 */

import dynamic from "next/dynamic"

const MarketingBackgroundLinesInner = dynamic(
  () => import("./marketing-background-lines").then((m) => m.MarketingBackgroundLines),
  { ssr: false },
)

export function MarketingBackgroundLines({ className }: { className?: string }) {
  return <MarketingBackgroundLinesInner className={className} />
}
