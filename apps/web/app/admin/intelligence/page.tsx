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
import { MemoryPromotionTab } from "./_components/memory-promotion-tab"
import { RelationshipsTab } from "./_components/relationships-tab"
import { EvaluationTab } from "./_components/evaluation-tab"
import { OutcomesTab } from "./_components/outcomes-tab"
import { EngineSettingsTab } from "./_components/engine-settings-tab"
import { PerformanceTab } from "./_components/performance-tab"

type TabKey = "overview" | "memory" | "relationships" | "evaluation" | "outcomes" | "engine" | "performance"

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
      <AppShell title="Intelligence">
        <EmptyState title="Sign in required" description="Log in to view org intelligence." />
      </AppShell>
    )
  }

  if (error) {
    const message = error instanceof ApiError ? error.message : "Failed to load intelligence data."
    return (
      <AppShell title="Intelligence">
        <ErrorState title="Unable to load intelligence" description={message} onRetry={() => mutate()} />
      </AppShell>
    )
  }

  return (
    <AppShell title="Intelligence">
      <div className="space-y-6 p-4 md:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground text-pretty">
            Query observability, memory promotion, entity relationships, response evaluation, and outcome-linked learning.
          </p>
          <Button variant="outline" size="sm" onClick={() => mutate()} disabled={isValidating}>
            <ArrowsClockwise className={`mr-2 h-4 w-4 ${isValidating ? "animate-spin" : ""}`} weight="bold" aria-hidden />
            Refresh
          </Button>
        </div>

        <Tabs value={tab} onValueChange={(value) => setTab(value as TabKey)}>
          <TabsList className="flex w-full flex-wrap justify-start">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="memory">Memory promotion</TabsTrigger>
            <TabsTrigger value="relationships">Relationships</TabsTrigger>
            <TabsTrigger value="evaluation">Evaluation</TabsTrigger>
            <TabsTrigger value="outcomes">Outcomes</TabsTrigger>
            <TabsTrigger value="engine">Engine</TabsTrigger>
            <TabsTrigger value="performance">Performance</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="mt-6">
            <OverviewTab data={data} isLoading={isLoading} />
          </TabsContent>

          <TabsContent value="memory" className="mt-6">
            <MemoryPromotionTab enabled={tab === "memory"} />
          </TabsContent>

          <TabsContent value="relationships" className="mt-6">
            <RelationshipsTab data={data} isLoading={isLoading} enabled={tab === "relationships"} />
          </TabsContent>

          <TabsContent value="evaluation" className="mt-6">
            <EvaluationTab enabled={tab === "evaluation"} />
          </TabsContent>

          <TabsContent value="outcomes" className="mt-6">
            <OutcomesTab enabled={tab === "outcomes"} />
          </TabsContent>

          <TabsContent value="engine" className="mt-6">
            <EngineSettingsTab enabled={tab === "engine"} />
          </TabsContent>

          <TabsContent value="performance" className="mt-6">
            <PerformanceTab enabled={tab === "performance"} />
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  )
}
