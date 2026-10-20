"use client"

import React, { useEffect, useState, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Loader2 } from "lucide-react"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import type { User } from "@/types/api"
import { OrganizationSettings } from "@/components/settings/organization-settings"
import { NotificationSettings } from "@/components/settings/notification-settings"
import { SecuritySettings } from "@/components/settings/security-settings"
import { TeamSettings } from "@/components/settings/team-settings"
import { ApiKeysSettings } from "@/components/settings/api-keys-settings"
import { AIModelsSettings } from "@/components/settings/ai-models-settings"
import { WebhooksSettings } from "@/components/settings/webhooks-settings"
import { MesonAddonsSettings } from "@/components/settings/meson-addons-settings"
import { LiteSeatsSettings } from "@/components/settings/lite-seats-settings"
import { EnterpriseWhiteLabel } from "@/components/settings/enterprise-white-label"
import { EnterpriseResidency } from "@/components/settings/enterprise-residency"
import { EnterpriseSiem } from "@/components/settings/enterprise-siem"
import "@/components/settings/enterprise-sections.css"
import { SettingsShell, canAccessSettingsSection } from "@/components/settings/settings-shell"
import { SETTINGS_SECTIONS, settingsHrefForSection, type SettingsSectionId } from "@/lib/settings-sections"
import { useOrgAdmin } from "@/lib/use-org-admin"

/** Redesigned sections that render their own SetHeader (title, lede and header actions). */
const OWN_HEADER_SECTIONS = new Set<SettingsSectionId>([
  "meson-addons",
  "security",
  "api-keys",
  "notifications",
  "ai-models",
  "team",
  "lite-seats",
])

function SettingsContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const { user } = useAuth()
  // `isAdmin` is server-confirmed and gates every admin-only control below;
  // `showAdmin` may come from the last confirmed answer cached for this
  // user + org, so the admin nav renders immediately and corrects itself.
  const { isAdmin, showAdmin, pending: adminPending } = useOrgAdmin()
  const sectionParam = (searchParams.get("section") || "organization") as SettingsSectionId
  const [activeSection, setActiveSection] = useState<SettingsSectionId>(sectionParam)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  useEffect(() => {
    const section = searchParams.get("section")
    if (section === "enterprise") {
      router.replace("/settings/enterprise")
      return
    }
    if (section === "federation") {
      router.replace("/settings/federation")
      return
    }
    if (section === "environments") {
      router.replace("/environments")
      return
    }
    if (section === "profile") {
      router.replace("/settings/profile")
      return
    }
    if (section === "organizations") {
      router.replace("/settings/organizations")
      return
    }
    if (section === "billing" || section === "billing-usage") {
      router.replace("/settings/billing")
      return
    }
    if (section === "approvals") {
      router.replace("/settings/approvals")
      return
    }
    if (section === "permissions") {
      router.replace("/settings/team/permissions")
      return
    }
    if (section === "audit") {
      router.replace("/audit")
      return
    }
    if (section === "mcp-servers") {
      router.replace(settingsHrefForSection("mcp-servers"))
      return
    }
    if (section) {
      setActiveSection(section as SettingsSectionId)
    }
  }, [searchParams, router])

  const { data: orgData, error: orgError, isLoading: orgLoading, mutate: mutateOrg } = useSWR(
    user ? "/api/settings/organization" : null,
    apiFetcher,
    { revalidateOnFocus: false }
  )

  const { data: teamData, error: teamError, isLoading: teamLoading, mutate: mutateTeam } = useSWR(
    user ? "/api/settings/team" : null,
    apiFetcher,
    { revalidateOnFocus: false }
  )

  const organization = (orgData as { organization?: Record<string, unknown> } | undefined)?.organization
  const team = ((teamData as { team?: User[] } | undefined)?.team ?? []) as User[]

  const renderContent = () => {
    if (!canAccessSettingsSection(activeSection, isAdmin)) {
      // Admin-only section before the role is confirmed: keep the settings
      // layout up and wait inline, instead of flashing "permission required"
      // at an admin (or blocking the whole page on the role round trip).
      if (adminPending || showAdmin) {
        return (
          <p role="status" className="py-6 text-sm text-muted-foreground">
            Checking admin access…
          </p>
        )
      }
      return (
        <div className="border-b border-divide py-3 text-sm text-muted-foreground">
          Admin or owner permission is required to manage this section.
        </div>
      )
    }

    if (activeSection === "organization" || !SETTINGS_SECTIONS.some(section => section.id === activeSection)) {
      if (orgLoading) return <p role="status" className="py-6 text-sm text-muted-foreground">Loading organization settings…</p>
      if (orgError || !organization) return <div role="alert" className="space-y-3 py-4">
        <p className="text-sm">Could not load organization settings. Try again before making changes.</p>
        <Button variant="outline" className="min-h-11" onClick={() => void mutateOrg()}>Retry organization</Button>
      </div>
    }
    switch (activeSection) {
      case "organization":
        return (
          <OrganizationSettings
            key={String(organization?.id ?? "organization")}
            orgData={organization!}
            isAdmin={isAdmin}
            onUpdate={async () => {
              await mutateOrg()
            }}
          />
        )
      case "ai-models": return <AIModelsSettings isAdmin={isAdmin} />
      case "security":
        // Data residency and SIEM export moved here from Enterprise: both are
        // about where workspace data lives and leaves, which admins look for
        // next to the access controls.
        return (
          <>
            <SecuritySettings isAdmin={isAdmin} />
            {isAdmin ? (
              <>
                <section aria-labelledby="security-residency-heading" className="mt-8 flex flex-col gap-3">
                  <h2 id="security-residency-heading" className="gs-eyebrow">Data residency</h2>
                  <EnterpriseResidency isAdmin={isAdmin} />
                </section>
                <section aria-labelledby="security-siem-heading" className="mt-8 flex flex-col gap-3">
                  <h2 id="security-siem-heading" className="gs-eyebrow">SIEM export</h2>
                  <EnterpriseSiem isAdmin={isAdmin} />
                </section>
              </>
            ) : null}
          </>
        )
      case "branding": return <EnterpriseWhiteLabel isAdmin={isAdmin} />
      case "api-keys": return <ApiKeysSettings isAdmin={isAdmin} />
      case "notifications": return <NotificationSettings isAdmin={isAdmin} />
      case "team":
        return (
          <TeamSettings
            members={team}
            isLoading={teamLoading}
            error={teamError}
            onRetry={() => void mutateTeam()}
            isAdmin={isAdmin}
            onUpdate={async () => {
              await mutateTeam()
            }}
          />
        )
      case "lite-seats":
        return <LiteSeatsSettings isAdmin={isAdmin} />
      case "meson-addons":
        return <MesonAddonsSettings isAdmin={isAdmin} />
      case "webhooks": return <WebhooksSettings isAdmin={isAdmin} />
      case "billing-usage":
      case "billing":
      case "approvals":
      case "permissions":
      case "audit":
      case "enterprise":
      case "federation":
      case "environments":
      case "profile":
      case "organizations":
      case "mcp-servers":
        return (
          <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Opening…
          </div>
        )
      default:
        return (
          <OrganizationSettings
            key={String(organization?.id ?? "organization")}
            orgData={organization!}
            isAdmin={isAdmin}
            onUpdate={async () => {
              await mutateOrg()
            }}
          />
        )
    }
  }

  const handleSectionChange = (section: SettingsSectionId) => {
    const href = settingsHrefForSection(section)
    if (href.startsWith("/settings?") || href === "/settings") {
      setActiveSection(section)
      router.push(href)
      return
    }
    router.push(href)
  }

  return (
    <div data-composition="configure" className="h-full min-h-0">
      <SettingsShell
      activeSection={activeSection}
      onSectionChange={handleSectionChange}
      isAdmin={showAdmin}
      hideHeader={OWN_HEADER_SECTIONS.has(activeSection) && canAccessSettingsSection(activeSection, isAdmin)}
      mobileMenuOpen={mobileMenuOpen}
      onMobileMenuOpenChange={setMobileMenuOpen}
    >
      {renderContent()}
      </SettingsShell>
    </div>
  )
}

export default function SettingsPage() {
  return (
    <AppShell title="Settings">
      <Suspense fallback={<div className="flex h-full items-center justify-center"><div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" /></div>}>
        <SettingsContent />
      </Suspense>
    </AppShell>
  )
}
