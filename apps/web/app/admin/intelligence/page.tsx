"use client"

import type { ReactNode } from "react"\nimport { PAGE_FRAME } from "@/lib/design-system"
import { useState } from "react"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAuth } from "@/lib/auth-context"
import { intelligenceApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { ArrowsClockwise, Graph, Pulse, SlidersHorizontal } from "@phosphor-icons/react"
import { OverviewTab } from "./_components/overview-tab"
import { BusinessImpactCard } from "./_components/business-impact-card"
import { ConnectorOpsCard } from "./_components/connector-ops-card"
import { KnowledgeFabricQualityCard } from "./_components/knowledge-fabric-quality-card"
import { MemoryPromotionTab } from "./_components/memory-promotion-tab"
import { RelationshipsTab } from "./_components/relationships-tab"
import { EvaluationTab } from "./_components/evaluation-tab"
import { OutcomesTab } from "./_components/outcomes-tab"
import { EngineTab } from "./_components/engine-tab"
import { PerformanceTab } from "./_components/performance-tab"
import { GoldenSignalsPanel } from "./_components/golden-signals-panel"
import { LearningTrendsTab } from "./_components/learning-trends-tab"
import { CognitiveTurnsTab } from "./_components/cognitive-turns-tab"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"

type TabKey =
  | "overview"
  | "memory"
  | "relationships"
  | "evaluation"
  | "outcomes"
  | "learning"
  | "engine"
  | "performance"
  | "cognitive"

function TabGroup({ label, icon, tabs }: { label: string; icon: ReactNode; tabs: [TabKey, string][] }) {
  return (
    <div className="rounded-[10px] border border-divide bg-[color:var(--g-surface-1)] p-2">
      <div className="mb-1.5 flex items-center gap-2 px-2 py-1 text-xs font-medium text-muted-foreground">
        {icon}<span>{label}</span>
      </div>
      <TabsList className="h-auto w-full justify-start gap-1 overflow-x-auto bg-transparent p-0 scrollbar-hide">
        {tabs.map(([value, text]) => (
          <TabsTrigger key={value} value={value} className="shrink-0 whitespace-nowrap px-2.5 py-1.5 text-xs data-[state=active]:bg-[color:var(--g-emerald-pale)] data-[state=active]:text-[color:var(--g-emerald-deep)]">
            {text}
          </TabsTrigger>
        ))}
      </TabsList>
    </div>
  )
}

export default function AdminIntelligencePage() {
  const { user } = useAuth()
  const [tab, setTab] = useState<TabKey>("overview")
  const copy = SURFACE_COPY.platformIntelligence
  const tabs = SURFACE_COPY.adminTabs

  const { data, error, isLoading, isValidating, mutate } = useSWR(
    user ? ["admin/intelligence/snapshot"] : null,
    () => intelligenceApi.snapshot(),
    { revalidateOnFocus: false },
  )

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to view platform intelligence." />
      </AppShell>
    )
  }

  if (error) {
    const message = error instanceof ApiError ? error.message : "Failed to load learning data."
    return (
      <AppShell title={copy.title}>
        <ErrorState title="Unable to load platform intelligence" description={message} onRetry={() => mutate()} />
      </AppShell>
    )
  }

  return (
    <AppShell title={copy.title}>
      <div className={PAGE_FRAME} data-composition="understand">
        <GravitrePageHeader
          title={copy.title}
          description={copy.description}
          icon={<NucleoIntelligence className="h-5 w-5" />}
          actions={
            <Button variant="outline" size="sm" onClick={() => mutate()} disabled={isValidating}>
              <ArrowsClockwise className={`mr-2 h-4 w-4 ${isValidating ? "animate-spin" : ""}`} weight="bold" aria-hidden />
              Refresh
            </Button>
          }
        />

        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
          <div>
            <p className="text-sm font-medium text-foreground">What do you need to inspect?</p>
            <p className="mt-1 max-w-2xl text-xs text-muted-foreground">
              Start with platform health, then move into learning, outcomes, or engineering diagnostics only when you need the detail.
            </p>
          </div>
          <div className="text-xs text-muted-foreground">Admin telemetry · read before tuning</div>
        </div>

        <Tabs value={tab} onValueChange={(value) => setTab(value as TabKey)} className="space-y-5">
          <div className="grid gap-2 lg:grid-cols-3">
            <TabGroup label="Health" icon={<Pulse className="h-4 w-4" />} tabs={[
              ["overview", tabs.overview], ["performance", "Performance"], ["cognitive", "Recent turns"],
            ]} />
            <TabGroup label="Intelligence" icon={<Graph className="h-4 w-4" />} tabs={[
              ["memory", tabs.memory], ["relationships", tabs.relationships], ["evaluation", tabs.evaluation], ["learning", tabs.learning],
            ]} />
            <TabGroup label="Impact & control" icon={<SlidersHorizontal className="h-4 w-4" />} tabs={[
              ["outcomes", tabs.outcomes], ["engine", tabs.engine],
            ]} />
          </div>

          <TabsContent value="overview" className="mt-0 space-y-5">
            <GoldenSignalsPanel />
            <div className="grid gap-5 xl:grid-cols-2">
              <BusinessImpactCard />
              <ConnectorOpsCard />
            </div>
            <KnowledgeFabricQualityCard />
            <OverviewTab data={data} isLoading={isLoading} />
          </TabsContent>
          <TabsContent value="memory" className="mt-0"><MemoryPromotionTab enabled={tab === "memory"} /></TabsContent>
          <TabsContent value="relationships" className="mt-0"><RelationshipsTab data={data} isLoading={isLoading} enabled={tab === "relationships"} /></TabsContent>
          <TabsContent value="evaluation" className="mt-0"><EvaluationTab enabled={tab === "evaluation"} /></TabsContent>
          <TabsContent value="outcomes" className="mt-0"><OutcomesTab enabled={tab === "outcomes"} /></TabsContent>
          <TabsContent value="learning" className="mt-0"><LearningTrendsTab enabled={tab === "learning"} /></TabsContent>
          <TabsContent value="engine" className="mt-0"><EngineTab enabled={tab === "engine"} /></TabsContent>
          <TabsContent value="performance" className="mt-0"><PerformanceTab enabled={tab === "performance"} /></TabsContent>
          <TabsContent value="cognitive" className="mt-0"><CognitiveTurnsTab enabled={tab === "cognitive"} /></TabsContent>
        </Tabs>
      </div>
    </AppShell>
  )
}
