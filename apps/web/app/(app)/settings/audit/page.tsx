"use client"

import { GovernanceSettingsPage } from "@/components/settings/governance-settings-page"
import { TrustSafetyAudit } from "@/components/trust-safety/trust-safety-audit"

export default function AuditSettingsPage() {
  return (
    <GovernanceSettingsPage section="audit">
      <TrustSafetyAudit />
    </GovernanceSettingsPage>
  )
}
