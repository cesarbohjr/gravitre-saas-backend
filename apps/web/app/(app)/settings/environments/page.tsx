"use client"

import { GovernanceSettingsPage } from "@/components/settings/governance-settings-page"
import { TrustSafetyEnvironments } from "@/components/trust-safety/trust-safety-environments"

export default function EnvironmentsSettingsPage() {
  return (
    <GovernanceSettingsPage section="environments">
      <TrustSafetyEnvironments />
    </GovernanceSettingsPage>
  )
}
