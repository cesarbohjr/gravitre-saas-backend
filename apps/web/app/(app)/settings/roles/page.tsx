"use client"

import { GovernanceSettingsPage } from "@/components/settings/governance-settings-page"
import { TrustSafetyRoles } from "@/components/trust-safety/trust-safety-roles"

export default function RolesSettingsPage() {
  return (
    <GovernanceSettingsPage section="roles">
      <TrustSafetyRoles />
    </GovernanceSettingsPage>
  )
}
