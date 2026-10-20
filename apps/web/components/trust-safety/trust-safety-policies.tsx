"use client"

import { ApprovalsContent } from "@/app/(app)/settings/approvals/page"

/**
 * Policies tab content for the Trust & Safety hub.
 * Renders the HITL approval policy management UI without the AppShell/SettingsShell wrappers.
 */
export function TrustSafetyPolicies() {
  return <ApprovalsContent />
}
