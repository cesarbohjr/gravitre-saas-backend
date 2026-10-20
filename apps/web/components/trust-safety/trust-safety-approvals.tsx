"use client"

import { Suspense } from "react"
import { DecisionQueue } from "@/app/(app)/approvals/page"

/**
 * Approvals tab content for the Trust & Safety hub.
 * Renders the decision queue without the AppShell wrapper.
 */
export function TrustSafetyApprovals() {
  return (
    <Suspense fallback={null}>
      <DecisionQueue />
    </Suspense>
  )
}
