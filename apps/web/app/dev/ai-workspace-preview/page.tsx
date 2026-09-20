/**
 * UX/UI 3.0 Plus design harness — isolated, unlinked, fixture-data only.
 * One harness. Not a second product runtime. Not authorized for production rollout.
 */

import { Suspense } from "react"
import type { Metadata } from "next"
import { DesignExplorationShell } from "./_components/design-exploration-shell"

export const metadata: Metadata = {
  title: "UX/UI 3.0 Plus design harness (internal)",
  robots: { index: false, follow: false },
}

export default function AiWorkspacePreviewPage() {
  return (
    <Suspense fallback={<p className="p-6 text-sm">Loading exploration…</p>}>
      <DesignExplorationShell />
    </Suspense>
  )
}
