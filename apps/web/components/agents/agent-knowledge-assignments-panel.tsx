"use client"

import { useState } from "react"
import useSWR from "swr"
import { Loader2, RefreshCw, Search } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { agentKnowledgeApi, type AgentKnowledgeAssignment } from "@/lib/api"

type AgentKnowledgeAssignmentsPanelProps = {
  agentId: string
}

function freshnessClass(status?: string): string {
  if (status === "fresh") return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
  if (status === "stale") return "bg-amber-500/10 text-amber-400 border-amber-500/20"
  if (status === "expired") return "bg-red-500/10 text-red-400 border-red-500/20"
  return "bg-secondary text-muted-foreground border-border"
}

export function AgentKnowledgeAssignmentsPanel({ agentId }: AgentKnowledgeAssignmentsPanelProps) {
  const [syncingId, setSyncingId] = useState<string | null>(null)
  const [testQuery, setTestQuery] = useState("brand guidelines")
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ matchCount: number } | null>(null)

  const { data, isLoading, mutate } = useSWR(
    agentId ? `agent/${agentId}/knowledge-assignments` : null,
    () => agentKnowledgeApi.listAssignments(agentId),
    { revalidateOnFocus: false }
  )
  const { data: capabilities } = useSWR(
    agentId ? `agent/${agentId}/capabilities` : null,
    () => agentKnowledgeApi.getCapabilities(agentId),
    { revalidateOnFocus: false }
  )

  const assignments = data?.assignments ?? []

  const handleSync = async (assignment: AgentKnowledgeAssignment) => {
    if (!assignment.id) {
      toast.error("Config-only sources must be migrated to managed assignments first.")
      return
    }
    try {
      setSyncingId(assignment.id)
      const result = await agentKnowledgeApi.syncAssignment(agentId, assignment.id)
      toast.success(result.message || "Sync completed")
      await mutate()
    } catch (error) {
      console.error("[knowledge] Sync failed:", error)
      toast.error("Sync failed")
    } finally {
      setSyncingId(null)
    }
  }

  const handleTestRetrieval = async () => {
    try {
      setTesting(true)
      const result = await agentKnowledgeApi.testRetrieval(agentId, testQuery)
      setTestResult({ matchCount: result.matchCount })
      toast.success(`Found ${result.matchCount} assigned matches`)
    } catch (error) {
      console.error("[knowledge] Test retrieval failed:", error)
      toast.error("Test retrieval failed")
    } finally {
      setTesting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-emerald-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {capabilities ? (
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "Assigned sources", value: capabilities.connectedKnowledgeSources?.length ?? 0 },
            { label: "Memory items", value: capabilities.memoryCount ?? 0 },
            { label: "Freshness", value: capabilities.freshnessStatus ?? "unknown" },
          ].map((stat) => (
            <div key={stat.label} className="rounded-xl border border-border bg-card p-4">
              <p className="text-lg font-bold text-foreground">{stat.value}</p>
              <p className="text-xs text-muted-foreground">{stat.label}</p>
            </div>
          ))}
        </div>
      ) : null}

      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label className="text-xs font-medium text-muted-foreground">Test retrieval</label>
            <Input
              value={testQuery}
              onChange={(event) => setTestQuery(event.target.value)}
              placeholder="Ask what this agent should know..."
              className="mt-1"
            />
          </div>
          <Button onClick={handleTestRetrieval} disabled={testing || !testQuery.trim()} className="gap-2">
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Test
          </Button>
        </div>
        {testResult ? (
          <p className="mt-2 text-xs text-muted-foreground">
            {testResult.matchCount} matching assigned source{testResult.matchCount === 1 ? "" : "s"} for this query.
          </p>
        ) : null}
      </div>

      {assignments.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-card/40 p-8 text-center">
          <p className="text-sm font-medium text-foreground">No assigned knowledge sources</p>
          <p className="mt-2 text-xs text-muted-foreground max-w-md mx-auto">
            Assign Google Drive folders, knowledge packs, or connector-backed sources so this agent only uses approved knowledge.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {assignments.map((assignment) => (
            <div
              key={assignment.id ?? `${assignment.sourceType}-${assignment.sourceId}`}
              className="flex items-center gap-4 rounded-xl border border-border bg-card p-4"
            >
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="font-medium text-foreground">{assignment.label}</h4>
                  <span className="rounded border px-2 py-0.5 text-[10px] font-medium uppercase text-muted-foreground">
                    {assignment.sourceType}
                  </span>
                  <span
                    className={cn(
                      "rounded border px-2 py-0.5 text-[10px] font-medium uppercase",
                      freshnessClass(assignment.freshnessStatus)
                    )}
                  >
                    {assignment.freshnessStatus || "unknown"}
                  </span>
                  {assignment.fromConfig ? (
                    <span className="rounded border border-border px-2 py-0.5 text-[10px] text-muted-foreground">
                      legacy config
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 text-xs text-muted-foreground truncate">{assignment.sourceId}</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="gap-2 shrink-0"
                disabled={!assignment.id || syncingId === assignment.id}
                onClick={() => handleSync(assignment)}
              >
                {syncingId === assignment.id ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
                Sync
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
