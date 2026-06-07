"use client"

<<<<<<< HEAD
import { useState } from "react"
import { AppShell } from "@/components/gravitre/app-shell"
import { PageHeader } from "@/components/gravitre/page-header"
import { useAuth } from "@/lib/auth-context"
import { cn } from "@/lib/utils"
import { Globe, Palette, Users, DollarSign, ShieldAlert, Lock } from "lucide-react"
import { RegionTab } from "@/components/enterprise/region-tab"
=======
import React, { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { PageHeader } from "@/components/gravitre/page-header"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { useAuth } from "@/lib/auth-context"
import { enterpriseApi } from "@/lib/api"
import { Building2, Lock } from "lucide-react"
import { EnterpriseSubNav } from "@/components/enterprise/enterprise-sub-nav"
import { DataRegionTab } from "@/components/enterprise/data-region-tab"
>>>>>>> eac2b609fbbcbbd202990b3258ff11c9e2f0003c
import { BrandingTab } from "@/components/enterprise/branding-tab"
import { WorkforceTab } from "@/components/enterprise/workforce-tab"
import { CostTab } from "@/components/enterprise/cost-tab"
import { SiemTab } from "@/components/enterprise/siem-tab"
<<<<<<< HEAD

type TabId = "region" | "branding" | "workforce" | "cost" | "siem"

const TABS: { id: TabId; label: string; icon: typeof Globe; description: string }[] = [
  { id: "region", label: "Data Residency", icon: Globe, description: "Control where your data is stored" },
  { id: "branding", label: "White Label", icon: Palette, description: "Custom logo, color, and domain" },
  { id: "workforce", label: "Workforce", icon: Users, description: "Agent task analytics" },
  { id: "cost", label: "Cost Attribution", icon: DollarSign, description: "Spend by agent and department" },
  { id: "siem", label: "SIEM Export", icon: ShieldAlert, description: "Stream audit logs to your SIEM" },
]

export default function EnterprisePage() {
  const [activeTab, setActiveTab] = useState<TabId>("region")
  const { user, loading } = useAuth()

  const role = user?.role
  const isAdmin = role === "admin" || role === "owner"

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-6xl px-4 py-6 md:px-6 md:py-8">
        <PageHeader
          title="Enterprise"
          description="Advanced controls for data residency, white labeling, workforce analytics, and security."
        />

        {!loading && !isAdmin ? (
          <div className="mt-8 flex flex-col items-center justify-center rounded-lg border border-border bg-card px-6 py-16 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
              <Lock className="h-6 w-6 text-muted-foreground" aria-hidden="true" />
            </div>
            <h2 className="mt-4 text-lg font-semibold text-foreground">Admin access required</h2>
            <p className="mt-1 max-w-sm text-sm text-muted-foreground text-pretty">
              Enterprise settings are only available to workspace owners and admins. Contact your administrator if you
              need access.
            </p>
          </div>
        ) : (
          <div className="mt-6 flex flex-col gap-6 lg:flex-row lg:gap-8">
            {/* Sub navigation */}
            <nav aria-label="Enterprise settings" className="lg:w-64 lg:shrink-0">
              {/* Mobile: horizontal scroll. Desktop: vertical list */}
              <div className="flex gap-2 overflow-x-auto pb-2 lg:flex-col lg:gap-1 lg:overflow-visible lg:pb-0">
                {TABS.map((tab) => {
                  const Icon = tab.icon
                  const active = activeTab === tab.id
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setActiveTab(tab.id)}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex shrink-0 items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors lg:w-full",
                        active
                          ? "border-primary/30 bg-primary/10 text-foreground"
                          : "border-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
                      )}
                    >
                      <Icon
                        className={cn("h-4 w-4 shrink-0", active ? "text-primary" : "text-muted-foreground")}
                        aria-hidden="true"
                      />
                      <span className="flex flex-col">
                        <span className="text-sm font-medium leading-tight">{tab.label}</span>
                        <span className="hidden text-xs text-muted-foreground lg:block">{tab.description}</span>
                      </span>
                    </button>
                  )
                })}
              </div>
            </nav>

            {/* Tab content */}
            <div className="min-w-0 flex-1">
              {activeTab === "region" && <RegionTab isAdmin={isAdmin} />}
              {activeTab === "branding" && <BrandingTab isAdmin={isAdmin} />}
              {activeTab === "workforce" && <WorkforceTab />}
              {activeTab === "cost" && <CostTab />}
              {activeTab === "siem" && <SiemTab isAdmin={isAdmin} />}
            </div>
          </div>
        )}
=======
import type { EnterpriseTabId } from "@/components/enterprise/types"

export default function EnterpriseSettingsPage() {
  const { user } = useAuth()
  const isAdmin = user?.role === "admin" || user?.role === "owner"
  const [activeTab, setActiveTab] = useState<EnterpriseTabId>("region")

  const { data: regionData, isLoading: regionLoading, mutate: mutateRegion } = useSWR(
    user ? "/api/enterprise/data-region" : null,
    () => enterpriseApi.getDataRegion(),
    { revalidateOnFocus: false }
  )
  const { data: brandingData, isLoading: brandingLoading, mutate: mutateBranding } = useSWR(
    user ? "/api/enterprise/branding" : null,
    () => enterpriseApi.getBranding(),
    { revalidateOnFocus: false }
  )
  const { data: analyticsData, isLoading: analyticsLoading } = useSWR(
    user && activeTab === "analytics" ? "/api/enterprise/workforce-analytics" : null,
    () => enterpriseApi.getWorkforceAnalytics(),
    { revalidateOnFocus: false }
  )
  const { data: costData, isLoading: costLoading } = useSWR(
    user && activeTab === "cost" ? "/api/enterprise/cost-attribution" : null,
    () => enterpriseApi.getCostAttribution(),
    { revalidateOnFocus: false }
  )
  const { data: siemData, isLoading: siemLoading, mutate: mutateSiem } = useSWR(
    user && isAdmin ? "/api/enterprise/siem" : null,
    () => enterpriseApi.getSiemConfig(),
    { revalidateOnFocus: false }
  )

  const [region, setRegion] = useState("us")
  const [logoUrl, setLogoUrl] = useState("")
  const [primaryColor, setPrimaryColor] = useState("#6366f1")
  const [customDomain, setCustomDomain] = useState("")
  const [domainVerified, setDomainVerified] = useState(false)
  const [hidePoweredBy, setHidePoweredBy] = useState(false)
  const [emailFromName, setEmailFromName] = useState("")
  const [siemEndpoint, setSiemEndpoint] = useState("")
  const [siemSecret, setSiemSecret] = useState("")
  const [siemEnabled, setSiemEnabled] = useState(false)

  React.useEffect(() => {
    if (regionData?.region) setRegion(regionData.region)
  }, [regionData])

  React.useEffect(() => {
    if (!brandingData) return
    setLogoUrl(String(brandingData.logoUrl ?? ""))
    setPrimaryColor(String(brandingData.primaryColor ?? "#6366f1"))
    setCustomDomain(String(brandingData.customDomain ?? ""))
    setDomainVerified(Boolean(brandingData.customDomainVerified))
    setHidePoweredBy(Boolean(brandingData.hidePoweredBy))
    setEmailFromName(String(brandingData.emailFromName ?? ""))
  }, [brandingData])

  React.useEffect(() => {
    if (!siemData) return
    setSiemEnabled(Boolean(siemData.enabled))
    setSiemEndpoint(String(siemData.endpoint ?? ""))
  }, [siemData])

  return (
    <AppShell title="Enterprise">
      <PageHeader
        title="Enterprise"
        description="Data residency, white-label branding, workforce analytics, and SIEM export"
        icon={Building2}
        iconColor="from-violet-500/20 to-indigo-500/20"
      >
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink asChild>
                <Link href="/settings">Settings</Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>Enterprise</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </PageHeader>

      <div className="mx-auto max-w-6xl p-4 md:p-6">
        {!isAdmin && (
          <Alert className="mb-6">
            <Lock className="h-4 w-4" />
            <AlertDescription>
              Admin access is required to change enterprise settings. Analytics and cost views are read-only.
            </AlertDescription>
          </Alert>
        )}

        <div className="flex flex-col gap-6 md:flex-row">
          <EnterpriseSubNav activeTab={activeTab} onTabChange={setActiveTab} />

          <div className="min-w-0 flex-1">
            {activeTab === "region" && (
              <DataRegionTab
                isAdmin={isAdmin}
                region={region}
                storagePrefix={regionData?.storagePrefix}
                isLoading={regionLoading}
                onRegionChange={setRegion}
                onSaved={async () => {
                  await mutateRegion()
                }}
              />
            )}
            {activeTab === "branding" && (
              <BrandingTab
                isAdmin={isAdmin}
                isLoading={brandingLoading}
                logoUrl={logoUrl}
                primaryColor={primaryColor}
                customDomain={customDomain}
                domainVerified={domainVerified}
                hidePoweredBy={hidePoweredBy}
                emailFromName={emailFromName}
                onLogoUrlChange={setLogoUrl}
                onPrimaryColorChange={setPrimaryColor}
                onCustomDomainChange={setCustomDomain}
                onHidePoweredByChange={setHidePoweredBy}
                onEmailFromNameChange={setEmailFromName}
                onSaved={async () => {
                  await mutateBranding()
                }}
              />
            )}
            {activeTab === "analytics" && (
              <WorkforceTab isLoading={analyticsLoading} analytics={analyticsData as Record<string, unknown>} />
            )}
            {activeTab === "cost" && (
              <CostTab isLoading={costLoading} cost={costData as Record<string, unknown>} />
            )}
            {activeTab === "siem" && (
              <SiemTab
                isAdmin={isAdmin}
                isLoading={siemLoading}
                siemEnabled={siemEnabled}
                siemEndpoint={siemEndpoint}
                siemSecret={siemSecret}
                hasSecret={siemData?.hasSecret}
                onEnabledChange={setSiemEnabled}
                onEndpointChange={setSiemEndpoint}
                onSecretChange={setSiemSecret}
                onSaved={async () => {
                  await mutateSiem()
                }}
              />
            )}
          </div>
        </div>
>>>>>>> eac2b609fbbcbbd202990b3258ff11c9e2f0003c
      </div>
    </AppShell>
  )
}
