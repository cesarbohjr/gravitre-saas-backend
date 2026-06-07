"use client"

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
import { BrandingTab } from "@/components/enterprise/branding-tab"
import { WorkforceTab } from "@/components/enterprise/workforce-tab"
import { CostTab } from "@/components/enterprise/cost-tab"
import { SiemTab } from "@/components/enterprise/siem-tab"
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
      </div>
    </AppShell>
  )
}
