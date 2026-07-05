"use client"

import { useState } from "react"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAuth } from "@/lib/auth-context"
import { intelligenceApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { ArrowsClockwise } from "@phosphor-icons/react"
import { OverviewTab } from "./_components/overview-tab"
import { BusinessImpactCard } from "./_components/business-impact-card"
import { MemoryPromotionTab } from "./_components/memory-promotion-tab"
import { RelationshipsTab } from "./_components/relationships-tab"
import { EvaluationTab } from "./_components/evaluation-tab"
import { OutcomesTab } from "./_components/outcomes-tab"
import { EngineTab } from "./_components/engine-tab"
import { PerformanceTab } from "./_components/performance-tab"
import { LearningTrendsTab } from "./_components/learning-trends-tab"
import { LearningSurfacesCallout } from "@/components/gravitre/learning-surfaces-callout"
import { PageHeader } from "@/components/gravitre/page-header"
import { Brain } from "lucide-react"

type TabKey = "overview" | "memory" | "relationships" | "evaluation" | "outcomes" | "learning" | "engine" | "performance"

export default function AdminIntelligencePage() {
  const { user } = useAuth()
  const [tab, setTab] = useState<TabKey>("overview")

  const { data, error, isLoading, isValidating, mutate } = useSWR(
    user ? ["admin/intelligence/snapshot"] : null,
    () => intelligenceApi.snapshot(),
    { revalidateOnFocus: false },
  )

  if (!user) {
    return (
      <AppShell title="Org Learning">
        <EmptyState title="Sign in required" description="Log in to view org learning." />
      </AppShell>
    )
  }

  if (error) {
    const message = error instanceof ApiError ? error.message : "Failed to load intelligence data."
    return (
      <AppShell title="Org Learning">
        <ErrorState title="Unable to load org learning" description={message} onRetry={() => mutate()} />
      </AppShell>
    )
  }

  return (
    <AppShell title="Org Learning">
      <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
        <LearningSurfacesCallout current="org-learning" />

        <PageHeader
          title="Org Learning"
          description="Monitor automatic learning from usage — query patterns, memory promotion, search quality, and outcome-linked signals."
          icon={Brain}
          iconColor="from-violet-500/20 to-emerald-500/20 ring-violet-500/20"
          className="rounded-2xl border border-border/70 bg-card/40 p-0 sm:p-0"
          actions={
            <Button variant="outline" size="sm" onClick={() => mutate()} disabled={isValidating}>
              <ArrowsClockwise className={`mr-2 h-4 w-4 ${isValidating ? "animate-spin" : ""}`} weight="bold" aria-hidden />
              Refresh
            </Button>
          }
        />

        <Tabs value={tab} onValueChange={(value) => setTab(value as TabKey)} className="space-y-6">
          <TabsList className="flex h-auto w-full flex-wrap justify-start gap-1 rounded-xl border border-border/70 bg-secondary/30 p-1">
            <TabsTrigger value="overview" className="rounded-lg data-[state=active]:bg-background data-[state=active]:shadow-sm">
              Overview
            </TabsTrigger>
            <TabsTrigger value="memory" className="rounded-lg data-[state=active]:bg-background data-[state=active]:shadow-sm">
              Memory promotion
            </TabsTrigger>
            <TabsTrigger value="relationships" className="rounded-lg data-[state=active]:bg-background data-[state=active]:shadow-sm">
              Relationships
            </TabsTrigger>
            <TabsTrigger value="evaluation" className="rounded-lg data-[state=active]:bg-background data-[state=active]:shadow-sm">
              Evaluation
            </TabsTrigger>
            <TabsTrigger value="outcomes" className="rounded-lg data-[state=active]:bg-background data-[state=active]:shadow-sm">
              Outcomes
            </TabsTrigger>
            <TabsTrigger value="learning" className="rounded-lg data-[state=active]:bg-background data-[state=active]:shadow-sm">
              Learning trends
            </TabsTrigger>
            <TabsTrigger value="engine" className="rounded-lg data-[state=active]:bg-background data-[state=active]:shadow-sm">
              Engine
            </TabsTrigger>
            <TabsTrigger value="performance" className="rounded-lg data-[state=active]:bg-background data-[state=active]:shadow-sm">
              Performance
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="mt-0 space-y-6">
            <BusinessImpactCard />
            <OverviewTab data={data} isLoading={isLoading} />
          </TabsContent>

          <TabsContent value="memory" className="mt-0">
            <MemoryPromotionTab enabled={tab === "memory"} />
          </TabsContent>

          <TabsContent value="relationships" className="mt-0">
            <RelationshipsTab data={data} isLoading={isLoading} enabled={tab === "relationships"} />
          </TabsContent>

          <TabsContent value="evaluation" className="mt-0">
            <EvaluationTab enabled={tab === "evaluation"} />
          </TabsContent>

          <TabsContent value="outcomes" className="mt-0">
            <OutcomesTab enabled={tab === "outcomes"} />
          </TabsContent>

          <TabsContent value="learning" className="mt-0">
            <LearningTrendsTab enabled={tab === "learning"} />
          </TabsContent>

          <TabsContent value="engine" className="mt-0">
            <EngineTab enabled={tab === "engine"} />
          </TabsContent>

          <TabsContent value="performance" className="mt-0">
            <PerformanceTab enabled={tab === "performance"} />
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  )
}
