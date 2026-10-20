"use client"

import { AuditTrail } from "@/components/settings/audit-trail"

/**
 * Audit Trail tab content for the Trust & Safety hub.
 * Renders the audit trail body without the SettingsShell wrapper.
 */
export function TrustSafetyAudit() {
  return <AuditTrail standalone />
}
