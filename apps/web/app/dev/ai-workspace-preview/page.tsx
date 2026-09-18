/**
 * UX Reset 2.0 design exploration — isolated, unlinked, mock-data only.
 * One harness. Not a second product runtime.
 */

import { Suspense } from "react"
import type { Metadata } from "next"
import { DesignExplorationShell } from "./_components/design-exploration-shell"

export const metadata: Metadata = {
  title: "UX Reset 2.0 design exploration (internal)",
  robots: { index: false, follow: false },
}

export default function AiWorkspacePreviewPage() {
  return (
    <Suspense fallback={<p className="p-6 text-sm">Loading exploration…</p>}>
      <DesignExplorationShell />
    </Suspense>
  )
}
