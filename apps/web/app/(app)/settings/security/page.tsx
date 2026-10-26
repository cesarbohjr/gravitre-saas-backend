"use client"

import { GovernanceSettingsPage } from "@/components/settings/governance-settings-page"
import { TrustSafetySecurity, useSecurityState } from "@/components/trust-safety/trust-safety-security"

function SecurityPanel() {
  const state = useSecurityState()
  return <TrustSafetySecurity state={state} />
}

export default function SecuritySettingsPage() {
  return (
    <GovernanceSettingsPage section="security">
      <SecurityPanel />
    </GovernanceSettingsPage>
  )
}
