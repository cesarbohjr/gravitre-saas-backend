"use client"

/**
 * AI-native primitives and Evil Charts on Carbon tokens. Board-only: every value
 * here is placeholder content and the charts are labelled as such on screen.
 */

import type { ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { ProviderLogo } from "@/components/gravitre/provider-logo"
import { PreActionCard } from "@/components/gravitre/pre-action-card"
import { ToolChip } from "@/components/gravitre/assistant/tool-chip"
import {
  ContextFacts,
  GravitreContextCard,
  GravitreTaskList,
  GravitreTaskRow,
  ReadinessCheck,
} from "@/components/gravitre/ai-native"
import { EChartsRadarChart } from "@/components/evilcharts/charts/echarts-radar-chart"
import { EChartsSankeyChart, type ChartConfig } from "@/components/evilcharts/charts/echarts-sankey-chart"
import { AUTONOMY_LEVELS } from "@/components/agents/agent-autonomy-panel"

function PlaceholderTag() {
  return (
    <span className="rounded-[4px] border border-[color:var(--g-border-strong)] px-1.5 py-0.5 text-[10.5px] font-medium uppercase tracking-wide text-muted-foreground">
      Placeholder data
    </span>
  )
}

function Panel({ title, children, tag }: { title: string; children: ReactNode; tag?: boolean }) {
  return (
    <div className="min-w-0 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-[12px] font-medium text-muted-foreground">{title}</h3>
        {tag ? <PlaceholderTag /> : null}
      </div>
      {children}
    </div>
  )
}

export function AiNativeBoard() {
  return (
    <div className="grid gap-8 lg:grid-cols-2">
      <Panel title="Task rows (runtime state only, no percentages)">
        <GravitreTaskList label="Run steps">
          <GravitreTaskRow state="done" title="Read HubSpot contacts" meta="12 records" />
          <GravitreTaskRow state="running" title="Enrich companies" detail="Apollo people.enrich" />
          <GravitreTaskRow
            state="waiting"
            title="Create HubSpot contact"
            detail="Waiting for approval"
            action={
              <Button size="sm" variant="outline" className="h-7 px-2 text-xs">
                Review
              </Button>
            }
          />
          <GravitreTaskRow state="blocked" title="Update Salesforce stage" detail="Missing scope: api" />
          <GravitreTaskRow state="failed" title="Post Slack summary" detail="channel_not_found" />
          <GravitreTaskRow state="pending" title="Write run summary" />
        </GravitreTaskList>
      </Panel>

      <Panel title="Context card">
        <GravitreContextCard
          kind="Connector"
          mark={<ProviderLogo provider="hubspot" size="lg" />}
          title="HubSpot"
          subtitle="CRM · production"
          status={<span className="text-[12px] text-muted-foreground">Connected</span>}
        >
          <ContextFacts
            facts={[
              { label: "Last sync", value: "4 min ago" },
              { label: "Sync frequency", value: "Hourly" },
              { label: "Records synced", value: null },
            ]}
          />
          <div className="mt-3 grid grid-cols-2 gap-1.5">
            <ReadinessCheck label="Authenticated" ok />
            <ReadinessCheck label="Token valid" ok />
            <ReadinessCheck label="Scopes valid" ok={false} />
            <ReadinessCheck label="Executable" ok={false} />
          </div>
        </GravitreContextCard>
      </Panel>

      <Panel title="Approval card (production PreActionCard)">
        <PreActionCard
          payload={{
            title: "Create HubSpot contact",
            description: "Priya Raman, Northwind Logistics",
            entity: "HubSpot · contacts",
            action: "hubspot.contacts.create",
            riskLevel: "medium",
            approvalReason: "Agent policy: every write needs approval",
            requiresApproval: true,
            source: "chat_pending",
          }}
          onApprove={() => {}}
          onReject={() => {}}
          onModify={() => {}}
        />
      </Panel>

      <Panel title="Tool chips (production ToolChip)">
        <ToolChip invocation={{ toolCallId: "b1", toolName: "getConnectorStatus", state: "result", result: { connectors: [{ name: "HubSpot", vendor: "hubspot", status: "connected", execution_available: true }] }, durationMs: 420 }} />
        <ToolChip invocation={{ toolCallId: "b2", toolName: "searchKnowledgeBase", state: "call" }} />
      </Panel>

      <Panel title="Autonomy levels (enforced trust_level)">
        <ol className="grid grid-cols-3 gap-px overflow-hidden rounded-md border border-[color:var(--g-border-default)] bg-[color:var(--g-border-subtle)]">
          {AUTONOMY_LEVELS.map((level, i) => {
            const Icon = level.icon
            return (
              <li key={level.id} className={cn("bg-card p-2.5", i === 1 && "shadow-[inset_0_2px_0_var(--signal-500)]")}>
                <Icon className="h-3.5 w-3.5 text-[color:var(--g-text-secondary)]" strokeWidth={1.75} aria-hidden />
                <p className="mt-1.5 text-[12px] font-medium text-foreground">{level.label}</p>
                <p className="mt-0.5 text-[11px] leading-4 text-muted-foreground">{level.summary}</p>
              </li>
            )
          })}
        </ol>
      </Panel>

      <Panel title="Radar (Evil Charts, Carbon styling)" tag>
        <BoardRadar />
      </Panel>

      <Panel title="Sankey (Evil Charts, counts only, no currency)" tag>
        <BoardSankey />
      </Panel>

      <p className={cn(TYPE.meta, "lg:col-span-2")}>
        Product agent detail shows the radar as “Not measured”: no per-dimension agent scores exist in the backend.
      </p>
    </div>
  )
}

const RADAR_DATA = [
  { dimension: "Read", agent: 5 },
  { dimension: "Write", agent: 3 },
  { dimension: "Approval", agent: 4 },
  { dimension: "Systems", agent: 2 },
  { dimension: "Limits", agent: 3 },
]

const RADAR_CONFIG: ChartConfig = {
  agent: { label: "Placeholder agent", colors: { light: ["#239b75"], dark: ["#2fbf8f"] } },
}

function BoardRadar() {
  return (
    <EChartsRadarChart data={RADAR_DATA} config={RADAR_CONFIG} className="h-[240px] w-full" animation={false}>
      <EChartsRadarChart.PolarGrid gridType="polygon" />
      <EChartsRadarChart.PolarAngleAxis dataKey="dimension" />
      <EChartsRadarChart.Radar dataKey="agent" variant="filled" fillOpacity={0.12}>
        <EChartsRadarChart.Dot />
      </EChartsRadarChart.Radar>
      <EChartsRadarChart.Tooltip roundness="sm" />
    </EChartsRadarChart>
  )
}

const SANKEY_CONFIG: ChartConfig = {
  crm: { label: "CRM", colors: { light: ["#5b6168"], dark: ["#9aa0a6"] } },
  support: { label: "Support", colors: { light: ["#5b6168"], dark: ["#9aa0a6"] } },
  passed: { label: "Passed", colors: { light: ["#239b75"], dark: ["#2fbf8f"] } },
  failed: { label: "Failed", colors: { light: ["#b3403f"], dark: ["#e07272"] } },
}

function BoardSankey() {
  return (
    <EChartsSankeyChart
      data={{
        nodes: [{ name: "crm" }, { name: "support" }, { name: "passed" }, { name: "failed" }],
        links: [
          { source: 0, target: 2, value: 8 },
          { source: 0, target: 3, value: 2 },
          { source: 1, target: 2, value: 5 },
          { source: 1, target: 3, value: 1 },
        ],
      }}
      config={SANKEY_CONFIG}
      className="h-[200px] w-full"
      nodeWidth={8}
      nodePadding={14}
      animationType="none"
    >
      <EChartsSankeyChart.Node radius={2}>
        <EChartsSankeyChart.NodeLabel position="outside" showValues />
      </EChartsSankeyChart.Node>
      <EChartsSankeyChart.Link variant="target" />
      <EChartsSankeyChart.Tooltip roundness="sm" />
    </EChartsSankeyChart>
  )
}
