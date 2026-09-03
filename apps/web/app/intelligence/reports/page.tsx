"use client"

import { useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { StatCard, StatsGrid } from "@/components/gravitre/page-header"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useAuth } from "@/lib/auth-context"
import { intelligenceApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { ApiError } from "@/lib/fetcher"
import {
  DEPARTMENTS,
  formatPercent,
  IntelligencePeriod,
  periodLabel,
  readNumber,
  readString,
} from "@/lib/intelligence/helpers"
import { ExecutiveIntelligenceScorecard } from "@/components/intelligence/executive-intelligence-scorecard"
import { PackKpiPanel } from "@/components/marketplace/pack-kpi-panel"
import { AgentRoiPanel } from "@/components/enterprise/agent-roi-panel"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { SURFACE_COPY } from "@/lib/surface-copy"

const reportsCopy = SURFACE_COPY.pages.reports

export default function IntelligenceReportsPage() {
  const { user } = useAuth()
  const [tab, setTab] = useState("roi")
  const [period, setPeriod] = useState<IntelligencePeriod>(7)

  const { data: outcomes, error, mutate, isLoading } = useSWR(
    user ? ["intelligence/reports/outcomes", period] : null,
    () => intelligenceApi.outcomes({ periodDays: period }),
    { revalidateOnFocus: false },
  )
  const { data: evaluations } = useSWR(user ? ["intelligence/reports/evaluations", period] : null, () =>
    intelligenceApi.intelligenceEvaluations({ periodDays: period }),
  )

  if (!user) {
    return (
      <AppShell title={reportsCopy.title}>
        <EmptyState title="Sign in required" description="Log in to view reports." />
      </AppShell>
    )
  }

  if (error) {
    return (
      <AppShell title={reportsCopy.title}>
        <ErrorState
          title="Unable to load reports"
          description={error instanceof ApiError ? error.message : "Please try again."}
          onRetry={() => mutate()}
        />
      </AppShell>
    )
  }

  const byEvent = (outcomes?.by_event_type as Record<string, number> | undefined) ?? {}
  const totalEvents = readNumber((outcomes?.summary as Record<string, unknown> | undefined)?.total_events, 0)
  const approvalRate = evaluations?.recommendation_approval_rate as number | null | undefined
  const orgId = typeof window !== "undefined" ? getSelectedOrgFromStorage()?.id : undefined

  return (
    <AppShell title={reportsCopy.title}>
      <div className="space-y-6 p-4 md:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground text-pretty">{reportsCopy.description}</p>
          {tab !== "roi" ? (
            <Select value={String(period)} onValueChange={(value) => setPeriod(Number(value) as IntelligencePeriod)}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="Period" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7">Last 7 days</SelectItem>
                <SelectItem value="30">Last 30 days</SelectItem>
                <SelectItem value="90">Last 90 days</SelectItem>
              </SelectContent>
            </Select>
          ) : null}
        </div>

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="flex flex-wrap">
            <TabsTrigger value="roi">{reportsCopy.tabRoi}</TabsTrigger>
            <TabsTrigger value="scorecards">{reportsCopy.tabScorecards}</TabsTrigger>
            <TabsTrigger value="executive">{reportsCopy.tabExecutive}</TabsTrigger>
            <TabsTrigger value="customer-success">{reportsCopy.tabCustomerSuccess}</TabsTrigger>
            <TabsTrigger value="prospecting">{reportsCopy.tabProspecting}</TabsTrigger>
            <TabsTrigger value="marketing">{reportsCopy.tabMarketing}</TabsTrigger>
            <TabsTrigger value="revops">{reportsCopy.tabRevOps}</TabsTrigger>
            <TabsTrigger value="ai-search">{reportsCopy.tabAiSearch}</TabsTrigger>
            <TabsTrigger value="finance">{reportsCopy.tabFinance}</TabsTrigger>
            <TabsTrigger value="hr-talent">{reportsCopy.tabHrTalent}</TabsTrigger>
            <TabsTrigger value="platform-health">{reportsCopy.tabPlatformHealth}</TabsTrigger>
          </TabsList>

          <TabsContent value="roi" className="mt-6 space-y-4">
            <AgentRoiPanel defaultPeriodDays={period === 7 ? 30 : period} />
            <p className="text-xs text-muted-foreground">
              Outcome events (period {periodLabel(period)}): {isLoading && !outcomes ? "…" : totalEvents}. Workflow /
              connector productivity still appears under scorecards and pack tabs.
            </p>
          </TabsContent>

          <TabsContent value="scorecards" className="mt-6 space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              {DEPARTMENTS.map((department) => {
                const benchmark = (
                  evaluations?.benchmark_status_by_department as Record<string, string> | undefined
                )?.[department]
                const deptEvents = readNumber(
                  (outcomes?.by_department as Record<string, number> | undefined)?.[department],
                  0,
                )
                const hasAgents = benchmark !== "not_configured" || deptEvents > 0
                return (
                  <article key={department} className="rounded-2xl border border-border/70 bg-card p-4">
                    <h3 className="font-semibold capitalize text-foreground">{department}</h3>
                    {!hasAgents ? (
                      <EmptyState
                        size="sm"
                        title={`No agents configured for ${department}`}
                        description="Install a department pack from the Marketplace to begin."
                        action={{
                          label: "Open Marketplace",
                          onClick: () => {
                            window.location.href = APP_ROUTES.marketplace
                          },
                          variant: "outline",
                        }}
                      />
                    ) : (
                      <StatsGrid columns={2} className="mt-3">
                        <StatCard label="Recommendations" value={readNumber(byEvent.recommendation_created, 0)} />
                        <StatCard
                          label="Acceptance rate"
                          value={approvalRate != null ? formatPercent(approvalRate) : "—"}
                        />
                        <StatCard label="Outcomes measured" value={deptEvents} />
                        <StatCard label="Benchmark" value={readString(benchmark, "—")} variant="info" />
                      </StatsGrid>
                    )}
                  </article>
                )
              })}
            </div>
            <Button variant="outline" size="sm" asChild>
              <Link href={APP_ROUTES.learning}>View learning evaluations</Link>
            </Button>
          </TabsContent>

          <TabsContent value="executive" className="mt-6 space-y-4">
            <PackKpiPanel
              packId="executive-intelligence-pack"
              packTitle="Executive Intelligence Pack"
            />
            <ExecutiveIntelligenceScorecard orgScopedKey={user && orgId ? `reports-${orgId}` : null} />
          </TabsContent>

          <TabsContent value="customer-success" className="mt-6 space-y-4">
            <PackKpiPanel
              packId="customer-success-intelligence-pack"
              packTitle="Customer Success Intelligence Pack"
            />
          </TabsContent>

          <TabsContent value="prospecting" className="mt-6 space-y-4">
            <PackKpiPanel
              packId="prospecting-intelligence-pack"
              packTitle="Prospecting & Lead Scouting Pack"
            />
          </TabsContent>

          <TabsContent value="marketing" className="mt-6 space-y-4">
            <PackKpiPanel
              packId="marketing-intelligence-pack"
              packTitle="Marketing Intelligence Pack"
            />
          </TabsContent>

          <TabsContent value="revops" className="mt-6 space-y-4">
            <PackKpiPanel
              packId="revops-intelligence-pack"
              packTitle="RevOps Intelligence Pack"
            />
          </TabsContent>

          <TabsContent value="ai-search" className="mt-6 space-y-4">
            <PackKpiPanel
              packId="ai-search-intelligence-pack"
              packTitle="AI Search Intelligence Pack"
            />
          </TabsContent>

          <TabsContent value="finance" className="mt-6 space-y-4">
            <PackKpiPanel
              packId="finance-intelligence-pack"
              packTitle="Finance Intelligence Pack"
            />
          </TabsContent>

          <TabsContent value="hr-talent" className="mt-6 space-y-4">
            <PackKpiPanel
              packId="hr-talent-intelligence-pack"
              packTitle="HR & Talent Intelligence Pack"
            />
          </TabsContent>

          <TabsContent value="platform-health" className="mt-6 space-y-4">
            <PackKpiPanel
              packId="platform-health-intelligence-pack"
              packTitle="Platform Health / Workflow Intelligence Pack"
            />
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  )
}
