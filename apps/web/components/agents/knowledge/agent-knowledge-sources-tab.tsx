"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { AssignmentKnowledgeCard, AgentKnowledgeCard } from "./agent-knowledge-card"
import type { AgentKnowledgeState } from "./use-agent-knowledge"
import { agentKnowledgeApi } from "@/lib/api"
import { toast } from "sonner"

export function AgentKnowledgeSourcesTab({
  workspace,
  agentId,
  agentName,
}: {
  workspace: AgentKnowledgeState
  agentId: string
  agentName: string
}) {
  const [query, setQuery] = useState("")
  const [typeFilter, setTypeFilter] = useState("all")
  const [syncingId, setSyncingId] = useState<string | null>(null)

  const assigned = workspace.assignments.filter((a) => a.enabled !== false)

  const filteredAvailable = useMemo(() => {
    const q = query.trim().toLowerCase()
    return workspace.orgSources.filter((s) => {
      if (workspace.assignedSourceIds.has(String(s.id))) return false
      if (typeFilter !== "all" && String(s.type ?? "") !== typeFilter) return false
      if (!q) return true
      return String(s.name ?? "").toLowerCase().includes(q)
    })
  }, [workspace.orgSources, workspace.assignedSourceIds, query, typeFilter])

  async function handleSync(assignmentId: string) {
    setSyncingId(assignmentId)
    try {
      const result = await agentKnowledgeApi.syncAssignment(agentId, assignmentId)
      toast.success(result.message || "Sync completed")
      await workspace.mutateAssignments()
    } catch {
      toast.error("Sync failed")
    } finally {
      setSyncingId(null)
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
        <div className="min-w-0 flex-1 space-y-1.5">
          <label htmlFor="kn-search" className="text-xs font-medium text-[color:var(--g-text-muted)]">
            Search knowledge
          </label>
          <Input
            id="kn-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search organization knowledge…"
          />
        </div>
        <div className="space-y-1.5">
          <span className="text-xs font-medium text-[color:var(--g-text-muted)]">Type</span>
          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="w-[160px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All types</SelectItem>
              <SelectItem value="file">Files</SelectItem>
              <SelectItem value="url">URL</SelectItem>
              <SelectItem value="database">Database</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <section className="space-y-3">
        <h2 className="text-xs font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
          Assigned to this agent
        </h2>
        {assigned.length === 0 ? (
          <div className="rounded-[var(--np-radius-lg)] border border-dashed border-divide bg-[color:var(--g-surface-2)]/40 px-6 py-10 text-center">
            <p className="text-sm font-medium text-[color:var(--g-text-primary)]">Give this agent something to work with.</p>
            <p className="mx-auto mt-2 max-w-md text-sm text-[color:var(--g-text-muted)]">
              Add company knowledge, expert intelligence, or connected sources so {agentName} can ground its decisions in
              information you trust.
            </p>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {assigned.map((assignment) => (
              <AssignmentKnowledgeCard
                key={assignment.id ?? `${assignment.sourceType}-${assignment.sourceId}`}
                assignment={assignment}
                ingestion={
                  assignment.sourceType === "rag_source"
                    ? workspace.sourceIngestionById.get(assignment.sourceId)
                    : undefined
                }
                busy={workspace.removingId === assignment.id || syncingId === assignment.id}
                onRemove={() => void workspace.removeAssignment(assignment)}
                onSync={
                  assignment.id && !assignment.fromConfig
                    ? () => void handleSync(assignment.id!)
                    : undefined
                }
              />
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-xs font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
            Available organization knowledge
          </h2>
          <Button type="button" variant="outline" size="sm" asChild>
            <Link href="/sources">Manage library</Link>
          </Button>
        </div>
        {workspace.orgSourcesLoading ? (
          <p className="text-sm text-muted-foreground">Loading organization sources…</p>
        ) : filteredAvailable.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No unassigned organization sources match your filters.{" "}
            <Link href="/sources" className="underline underline-offset-2">
              Add sources in the library
            </Link>
            .
          </p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {filteredAvailable.slice(0, 24).map((source) => (
              <AgentKnowledgeCard
                key={String(source.id)}
                title={String(source.name ?? "Source")}
                description={String(source.description ?? "")}
                sourceType="rag_source"
                status={String(source.status ?? "unknown")}
                meta={String(source.type ?? "")}
                ingestion={workspace.sourceIngestionById.get(String(source.id))}
                detailHref={`/sources/${encodeURIComponent(String(source.id))}/agents`}
                busy={workspace.assigningKey === `source:${source.id}`}
                onAssign={() =>
                  void workspace.assignOrgSource({
                    id: String(source.id),
                    name: String(source.name ?? "Source"),
                  })
                }
              />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
