"use client"

import { useState } from "react"
import { AppShell } from "@/components/gravitre/app-shell"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Compass, Brain, Graph, Gauge } from "@phosphor-icons/react"
import { OverviewTab } from "./_components/overview-tab"
import { MemoryPromotionTab } from "./_components/memory-promotion-tab"
import { RelationshipsTab } from "./_components/relationships-tab"
import { EvaluationTab } from "./_components/evaluation-tab"

const TABS = [
  { value: "overview", label: "Overview", Icon: Compass },
  { value: "memory-promotion", label: "Memory Promotion", Icon: Brain },
  { value: "relationships", label: "Relationships", Icon: Graph },
  { value: "evaluation", label: "Evaluation", Icon: Gauge },
] as const

export default function IntelligencePage() {
  const [tab, setTab] = useState<string>("overview")

  return (
    <AppShell title="Intelligence">
      <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
        <header className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground text-balance">
            Knowledge Intelligence
          </h1>
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted-foreground text-pretty">
            How your knowledge engine learns: what it is retrieving, which agent memories generalize,
            how entities connect, and how response quality is scored over time.
          </p>
        </header>

        <Tabs value={tab} onValueChange={setTab} className="w-full">
          <TabsList className="mb-6 flex h-auto w-full flex-wrap justify-start gap-1 bg-secondary/60 p-1">
            {TABS.map(({ value, label, Icon }) => (
              <TabsTrigger
                key={value}
                value={value}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm data-[state=active]:bg-background"
              >
                <Icon className="h-4 w-4" weight="duotone" aria-hidden />
                {label}
              </TabsTrigger>
            ))}
          </TabsList>

          <TabsContent value="overview">
            <OverviewTab active={tab === "overview"} />
          </TabsContent>
          <TabsContent value="memory-promotion">
            <MemoryPromotionTab active={tab === "memory-promotion"} />
          </TabsContent>
          <TabsContent value="relationships">
            <RelationshipsTab active={tab === "relationships"} />
          </TabsContent>
          <TabsContent value="evaluation">
            <EvaluationTab active={tab === "evaluation"} />
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  )
}
