"use client"

import { useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import useSWR from "swr"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { useAuth } from "@/lib/auth-context"
import { agentKnowledgeApi, sourcesApi } from "@/lib/api"
import { buildOrgSourceAssignmentPayload } from "@/lib/agent-knowledge-assign"
import { ArrowLeft, Check, Plus } from "@phosphor-icons/react"
import { cn } from "@/lib/utils"

type AgentAssignmentRow = {
  agentId: string
  agentName: string
  department?: string
  role?: string
  assigned: boolean
  assignmentId?: string | null
}

export default function SourceAgentAssignmentsPage() {
  const params = useParams()
  const sourceId = String(params.id ?? "")
  const { user } = useAuth()
  const [busyAgentId, setBusyAgentId] = useState<string | null>(null)

  const { data, isLoading, mutate } = useSWR(
    user && sourceId ? `/api/sources/${sourceId}/agent-assignments` : null,
    () => sourcesApi.listAgentAssignments(sourceId),
  )

  const { data: sourceData } = useSWR(
    user && sourceId ? `/api/sources/${sourceId}` : null,
    () => sourcesApi.get(sourceId),
  )

  const sourceName = data?.sourceName ?? sourceData?.source?.name ?? "Knowledge base"
  const agents = (data?.agents ?? []) as AgentAssignmentRow[]
  const assignedCount = data?.assignedCount ?? agents.filter((a) => a.assigned).length

  async function toggleAgent(row: AgentAssignmentRow) {
    setBusyAgentId(row.agentId)
    try {
      if (row.assigned && row.assignmentId) {
        await agentKnowledgeApi.deleteAssignment(row.agentId, row.assignmentId)
        toast.success(`${row.agentName} unassigned — knowledge base was not deleted`)
      } else {
        await agentKnowledgeApi.createAssignment(
          row.agentId,
          buildOrgSourceAssignmentPayload({ id: sourceId, name: sourceName }),
        )
        toast.success(`${sourceName} assigned to ${row.agentName}`)
      }
      await mutate()
    } catch (error) {
      console.error("[source-agents] toggle failed:", error)
      toast.error(`Couldn't update assignment for ${row.agentName}`)
    } finally {
      setBusyAgentId(null)
    }
  }

  return (
    <AppShell title={`${sourceName} — Agents`}>
      <div className="mx-auto max-w-3xl space-y-6 p-4 sm:p-6">
        <Link
          href={`/sources/${sourceId}`}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          Back to source
        </Link>

        <GravitrePageHeader
          eyebrow="Organization knowledge"
          title={sourceName}
          description={`Used by ${assignedCount} agent${assignedCount === 1 ? "" : "s"}. Assign or remove without deleting the underlying knowledge base.`}
        />

        {isLoading ? (
          <div className="flex justify-center py-16">
            <Spinner size="lg" />
          </div>
        ) : agents.length === 0 ? (
          <p className="text-sm text-muted-foreground">No agents in this organization yet.</p>
        ) : (
          <ul className="divide-y divide-border rounded-xl border border-border/70">
            {agents.map((row) => (
              <li key={row.agentId} className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <p className="font-medium text-foreground">{row.agentName}</p>
                  <p className="text-xs text-muted-foreground">
                    {[row.department, row.role].filter(Boolean).join(" · ")}
                  </p>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant={row.assigned ? "secondary" : "outline"}
                  disabled={busyAgentId === row.agentId}
                  className={cn("gap-1.5 shrink-0", row.assigned && "border-emerald-500/30")}
                  onClick={() => void toggleAgent(row)}
                >
                  {row.assigned ? (
                    <>
                      <Check className="h-4 w-4" weight="bold" aria-hidden />
                      Assigned
                    </>
                  ) : (
                    <>
                      <Plus className="h-4 w-4" weight="bold" aria-hidden />
                      Assign
                    </>
                  )}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </AppShell>
  )
}
