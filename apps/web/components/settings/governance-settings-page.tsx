"use client"

import { Suspense, type ReactNode } from "react"
import { AppShell } from "@/components/gravitre/app-shell"
import { AccessArt } from "@/components/agents/art/agents-art"
import { AuditArt, SecurityArt } from "@/components/dashboard/art/dashboard-art"
import { TrustSafetyArtOverrides } from "@/components/trust-safety/trust-safety-art"
import { SettingsShell, canAccessSettingsSection } from "@/components/settings/settings-shell"
import { useSettingsSectionNav } from "@/lib/settings-nav"
import { useOrgAdmin } from "@/lib/use-org-admin"
import type { SettingsSectionId } from "@/lib/settings-sections"
import "@/app/(app)/trust-safety/gv-trust.css"
import "./governance-settings.css"

const ART_OVERRIDES = { security: <SecurityArt />, audit: <AuditArt /> }

type GovernanceSection = Extract<SettingsSectionId, "security" | "roles" | "audit" | "environments">

const CRUMBS: Record<GovernanceSection, string> = {
  security: "Settings / Workspace",
  roles: "Access control",
  audit: "Governance",
  environments: "Governance / Infrastructure",
}

/**
 * Settings pages built on the Trust & Safety panels (Dashboard settings design):
 * the settings rail and header around the same live controls the Trust & Safety tabs use.
 */
export function GovernanceSettingsPage({ section, children }: { section: GovernanceSection; children: ReactNode }) {
  const { isAdmin, showAdmin, pending } = useOrgAdmin()
  const onSectionChange = useSettingsSectionNav(section)
  const allowed = canAccessSettingsSection(section, isAdmin)

  let body: ReactNode = children
  if (!allowed) {
    body =
      pending || showAdmin ? (
        <p role="status" className="py-6 text-sm text-muted-foreground">
          Checking admin access…
        </p>
      ) : (
        <section className="gs-locked" aria-label="Admins only">
          <div className="gs-locked-art">
            <AccessArt />
          </div>
          <div className="gs-locked-copy">
            <b>Admins only</b>
            <span>An owner or admin of this workspace can manage this section. Ask one of them to change it, or to give you the admin role.</span>
          </div>
        </section>
      )
  }

  return (
    <AppShell title="Settings">
      <div data-composition="configure" className="h-full min-h-0">
        <Suspense fallback={null}>
          <SettingsShell activeSection={section} isAdmin={showAdmin} onSectionChange={onSectionChange} crumb={CRUMBS[section]}>
            <TrustSafetyArtOverrides.Provider value={ART_OVERRIDES}>
              <div className="ts-root gs-ts">{body}</div>
            </TrustSafetyArtOverrides.Provider>
          </SettingsShell>
        </Suspense>
      </div>
    </AppShell>
  )
}
