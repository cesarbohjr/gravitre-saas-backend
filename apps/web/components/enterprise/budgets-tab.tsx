"use client"

import { useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { Gauge, Bot, Save } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"
import { AdaptiveDataView } from "@/components/gravitre/adaptive-data-view"
import { enterpriseApi } from "@/lib/api"
import type {
  AgentAutonomousRunBudgetStatus,
  AutonomousRunBudgetLimits,
  EnterpriseAutonomousRunBudgets,
} from "@/types/api"
import { TabSkeleton } from "./enterprise-skeletons"

function formatUsd(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n || 0)
}

function formatLimit(value: number | null | undefined): string {
  if (value == null) return "—"
  return String(value)
}

function usagePct(used: number, limit: number | null | undefined): number | null {
  if (limit == null || limit <= 0) return null
  return Math.min(100, Math.round((used / limit) * 100))
}

function OrgDefaultsForm({
  defaults,
  isAdmin,
  onSaved,
}: {
  defaults: AutonomousRunBudgetLimits
  isAdmin: boolean
  onSaved: () => void
}) {
  const [maxActions, setMaxActions] = useState(defaults.maxActionsPerDay?.toString() ?? "")
  const [maxTokens, setMaxTokens] = useState(defaults.maxTokensPerDay?.toString() ?? "")
  const [maxSpend, setMaxSpend] = useState(defaults.maxSpendUsdPerDay?.toString() ?? "")
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    setSaving(true)
    try {
      await enterpriseApi.updateAutonomousRunBudgets({
        maxActionsPerDay: maxActions.trim() ? Number(maxActions) : null,
        maxTokensPerDay: maxTokens.trim() ? Number(maxTokens) : null,
        maxSpendUsdPerDay: maxSpend.trim() ? Number(maxSpend) : null,
        unset: [
          ...(maxActions.trim() ? [] : ["maxActionsPerDay"]),
          ...(maxTokens.trim() ? [] : ["maxTokensPerDay"]),
          ...(maxSpend.trim() ? [] : ["maxSpendUsdPerDay"]),
        ],
      })
      toast.success("Org-wide run budgets saved")
      onSaved()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save org budgets")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Gauge className="h-4 w-4 text-primary" />
          <CardTitle className="text-base">Org-wide defaults</CardTitle>
        </div>
        <CardDescription>
          Daily caps for agents in auto-execute mode. Per-agent overrides take precedence when set.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="org-max-actions">Max actions / day</Label>
            <Input
              id="org-max-actions"
              type="number"
              min={0}
              placeholder="No limit"
              value={maxActions}
              onChange={(e) => setMaxActions(e.target.value)}
              disabled={!isAdmin}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="org-max-tokens">Max tokens / day</Label>
            <Input
              id="org-max-tokens"
              type="number"
              min={0}
              placeholder="No limit"
              value={maxTokens}
              onChange={(e) => setMaxTokens(e.target.value)}
              disabled={!isAdmin}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="org-max-spend">Max spend (USD) / day</Label>
            <Input
              id="org-max-spend"
              type="number"
              min={0}
              step="0.01"
              placeholder="No limit"
              value={maxSpend}
              onChange={(e) => setMaxSpend(e.target.value)}
              disabled={!isAdmin}
            />
          </div>
        </div>
        {isAdmin ? (
          <Button type="button" onClick={handleSave} disabled={saving}>
            <Save className="mr-2 h-4 w-4" />
            {saving ? "Saving…" : "Save org defaults"}
          </Button>
        ) : null}
      </CardContent>
    </Card>
  )
}

function AgentBudgetRow({
  agent,
  isAdmin,
  onSaved,
}: {
  agent: AgentAutonomousRunBudgetStatus
  isAdmin: boolean
  onSaved: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [maxActions, setMaxActions] = useState(agent.limits.maxActionsPerDay?.toString() ?? "")
  const [maxTokens, setMaxTokens] = useState(agent.limits.maxTokensPerDay?.toString() ?? "")
  const [maxSpend, setMaxSpend] = useState(agent.limits.maxSpendUsdPerDay?.toString() ?? "")
  const [saving, setSaving] = useState(false)

  const actionPct = usagePct(agent.usageToday.actions, agent.limits.maxActionsPerDay)
  const tokenPct = usagePct(agent.usageToday.tokens, agent.limits.maxTokensPerDay)
  const spendPct = usagePct(agent.usageToday.spendUsd, agent.limits.maxSpendUsdPerDay)

  async function handleSave() {
    setSaving(true)
    try {
      await enterpriseApi.updateAgentRunBudgets(agent.agentId, {
        maxActionsPerDay: maxActions.trim() ? Number(maxActions) : null,
        maxTokensPerDay: maxTokens.trim() ? Number(maxTokens) : null,
        maxSpendUsdPerDay: maxSpend.trim() ? Number(maxSpend) : null,
        unset: [
          ...(maxActions.trim() ? [] : ["maxActionsPerDay"]),
          ...(maxTokens.trim() ? [] : ["maxTokensPerDay"]),
          ...(maxSpend.trim() ? [] : ["maxSpendUsdPerDay"]),
        ],
      })
      toast.success(`Budgets updated for ${agent.name}`)
      setEditing(false)
      onSaved()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save agent budgets")
    } finally {
      setSaving(false)
    }
  }

  return (
    <tr className="border-b border-border last:border-0">
      <td className="py-3 pr-4">
        <div className="flex flex-col gap-1">
          <span className="font-medium text-foreground">{agent.name}</span>
          <Badge variant="outline" className="w-fit text-[10px] uppercase tracking-wide">
            {agent.executionMode.replace(/_/g, " ")}
          </Badge>
        </div>
      </td>
      <td className="py-3 pr-4 text-sm tabular-nums text-muted-foreground">
        {agent.usageToday.actions}
        {actionPct != null ? <span className="ml-1 text-xs">({actionPct}%)</span> : null}
        <span className="mx-1 text-muted-foreground/40">/</span>
        {formatLimit(agent.limits.maxActionsPerDay)}
      </td>
      <td className="py-3 pr-4 text-sm tabular-nums text-muted-foreground">
        {Math.round(agent.usageToday.tokens).toLocaleString()}
        {tokenPct != null ? <span className="ml-1 text-xs">({tokenPct}%)</span> : null}
        <span className="mx-1 text-muted-foreground/40">/</span>
        {formatLimit(agent.limits.maxTokensPerDay)}
      </td>
      <td className="py-3 pr-4 text-sm tabular-nums text-muted-foreground">
        {formatUsd(agent.usageToday.spendUsd)}
        {spendPct != null ? <span className="ml-1 text-xs">({spendPct}%)</span> : null}
        <span className="mx-1 text-muted-foreground/40">/</span>
        {agent.limits.maxSpendUsdPerDay != null ? formatUsd(agent.limits.maxSpendUsdPerDay) : "—"}
      </td>
      <td className="py-3 text-right">
        {isAdmin && !editing ? (
          <Button type="button" variant="outline" size="sm" onClick={() => setEditing(true)}>
            Edit
          </Button>
        ) : null}
        {isAdmin && editing ? (
          <div className="flex flex-col items-end gap-2">
            <div className="grid grid-cols-3 gap-2">
              <Input
                type="number"
                min={0}
                placeholder="Actions"
                value={maxActions}
                onChange={(e) => setMaxActions(e.target.value)}
                className="h-8 w-24"
              />
              <Input
                type="number"
                min={0}
                placeholder="Tokens"
                value={maxTokens}
                onChange={(e) => setMaxTokens(e.target.value)}
                className="h-8 w-24"
              />
              <Input
                type="number"
                min={0}
                step="0.01"
                placeholder="USD"
                value={maxSpend}
                onChange={(e) => setMaxSpend(e.target.value)}
                className="h-8 w-24"
              />
            </div>
            <div className="flex gap-2">
              <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(false)}>
                Cancel
              </Button>
              <Button type="button" size="sm" onClick={handleSave} disabled={saving}>
                Save
              </Button>
            </div>
          </div>
        ) : null}
      </td>
    </tr>
  )
}

export function BudgetsTab({ isAdmin }: { isAdmin: boolean }) {
  const { data, isLoading, mutate } = useSWR<EnterpriseAutonomousRunBudgets>(
    "enterprise-run-budgets",
    () => enterpriseApi.getAutonomousRunBudgets(),
    { revalidateOnFocus: false },
  )

  if (isLoading) return <TabSkeleton rows={4} />
  if (!data) return null

  const autoAgents = data.agents.filter((a) => a.executionMode !== "plan_only")

  return (
    <div className="space-y-4">
      <OrgDefaultsForm
        key={`org-${JSON.stringify(data.orgDefaults)}`}
        defaults={data.orgDefaults}
        isAdmin={isAdmin}
        onSaved={() => mutate()}
      />

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 text-primary" />
            <CardTitle className="text-base">Agent usage today</CardTitle>
          </div>
          <CardDescription>
            UTC day {data.agents[0]?.usageDate ?? "—"}. Showing {autoAgents.length} agents with auto-execute enabled.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {autoAgents.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No agents are in auto-execute mode yet. Enable auto-execute on an agent to enforce daily budgets.
            </p>
          ) : (
            <AdaptiveDataView className="border-0">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="pb-2 pr-4 font-medium">Agent</th>
                    <th className="pb-2 pr-4 font-medium">Actions</th>
                    <th className="pb-2 pr-4 font-medium">Tokens</th>
                    <th className="pb-2 pr-4 font-medium">Spend</th>
                    <th className="pb-2 text-right font-medium">Limits</th>
                  </tr>
                </thead>
                <tbody>
                  {autoAgents.map((agent) => (
                    <AgentBudgetRow
                      key={agent.agentId}
                      agent={agent}
                      isAdmin={isAdmin}
                      onSaved={() => mutate()}
                    />
                  ))}
                </tbody>
              </table>
            </AdaptiveDataView>
          )}
          <Separator className="my-4" />
          <p className={cn("text-xs text-muted-foreground")}>
            Token and spend rollups update on each LLM call during autonomous runs. Tool actions count toward the actions
            cap.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
