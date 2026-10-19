"use client"

/**
 * Settings > Enterprise (design p18). Admin only, reports only. A left section
 * menu (aria-pressed, linkable through ?section=) switches between Command
 * center, Workforce, Cost attribution and Agent ROI. Knowledge sync moved to
 * Connectors, White label to Settings > Branding, Data residency and SIEM
 * export to Settings > Security; old links to them redirect there. Each
 * section lives in components/settings/enterprise-*.tsx and reads real data only.
 */
import { Suspense, useEffect } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import {
  DollarSign,
  HeartPulse,
  LineChart,
  Users,
  type LucideIcon,
} from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { SettingsShell } from "@/components/settings/settings-shell"
import { SetNote, SetSkeleton } from "@/components/settings/settings-kit"
import { PlatformOrgViewBanner } from "@/components/enterprise/platform-org-view-banner"
import { EnterpriseCommandCenter } from "@/components/settings/enterprise-command-center"
import { EnterpriseWorkforce } from "@/components/settings/enterprise-workforce"
import { EnterpriseCost } from "@/components/settings/enterprise-cost"
import { EnterpriseRoi } from "@/components/settings/enterprise-roi"
import "@/components/settings/enterprise-sections.css"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { fetcher } from "@/lib/fetcher"
import {
  movedEnterpriseSectionHref,
  resolveEnterpriseSection,
  type EnterpriseSectionId,
} from "@/lib/settings-api/enterprise"

const SECTIONS: { id: EnterpriseSectionId; label: string; description: string; icon: LucideIcon }[] = [
  { id: "command-center", label: "Command center", description: "Integration health and recommendations", icon: HeartPulse },
  { id: "workforce", label: "Workforce", description: "Agent task counts by team", icon: Users },
  { id: "cost", label: "Cost attribution", description: "Spend by agent and department", icon: DollarSign },
  { id: "agent-roi", label: "Agent ROI", description: "Cost against estimated labor value", icon: LineChart },
]

export default function EnterprisePage() {
  return (
    <Suspense fallback={null}>
      <EnterprisePageContent />
    </Suspense>
  )
}

function EnterprisePageContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const pathname = usePathname()
  // The URL is the source of truth for the section, so sections can be linked.
  const active = resolveEnterpriseSection(searchParams.get("section"), searchParams.get("tab"))
  const movedHref = movedEnterpriseSectionHref(searchParams.get("section"), searchParams.get("tab"))
  useEffect(() => {
    if (movedHref) router.replace(movedHref)
  }, [movedHref, router])
  const { user, loading } = useAuth()
  const { data: me } = useSWR(user ? "/api/auth/me" : null, fetcher)
  const isPlatformAdmin = Boolean((me as { platformAdmin?: boolean } | undefined)?.platformAdmin)
  const { isAdmin, showAdmin, pending } = useOrgAdmin()
  const canAct = isAdmin || isPlatformAdmin
  const canSee = showAdmin || isPlatformAdmin

  const select = (id: EnterpriseSectionId) => {
    const params = new URLSearchParams(Array.from(searchParams.entries()))
    params.delete("tab")
    params.set("section", id)
    router.replace(`${pathname}?${params.toString()}`, { scroll: false })
  }

  return (
    <AppShell title="Settings">
      <SettingsShell activeSection="enterprise" isAdmin={canSee}>
        <PlatformOrgViewBanner />
        {loading || (pending && !canSee) ? (
          <section className="gs-card">
            <SetSkeleton rows={3} label="Checking admin access" />
          </section>
        ) : !canSee ? (
          <SetNote>
            Enterprise settings are only available to workspace owners and admins. Ask your administrator if you need
            access.
          </SetNote>
        ) : (
          <div className="ent-layout">
            <nav aria-label="Enterprise settings" className="ent-menu">
              {SECTIONS.map((section) => {
                const Icon = section.icon
                const on = section.id === active
                return (
                  <button
                    key={section.id}
                    type="button"
                    className="ent-sub"
                    aria-pressed={on}
                    onClick={() => select(section.id)}
                  >
                    <span className="gs-ico mute" aria-hidden>
                      <Icon size={16} aria-hidden />
                    </span>
                    <span style={{ minWidth: 0 }}>
                      <b>{section.label}</b>
                      <small>{section.description}</small>
                    </span>
                  </button>
                )
              })}
            </nav>
            <div className="ent-body">
              {active === "command-center" && <EnterpriseCommandCenter />}
              {active === "workforce" && <EnterpriseWorkforce />}
              {active === "cost" && <EnterpriseCost />}
              {active === "agent-roi" && <EnterpriseRoi isAdmin={canAct} />}
            </div>
          </div>
        )}
      </SettingsShell>
    </AppShell>
  )
}
