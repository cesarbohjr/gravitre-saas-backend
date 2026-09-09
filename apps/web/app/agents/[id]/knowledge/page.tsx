"use client"

import { use, useMemo, useState, useEffect, Suspense } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import useSWR from "swr"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitreMetric, GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { Icon } from "@/lib/icons"
import { NavDatabase } from "@/components/icons/nodus-nav/outline"
import { cn } from "@/lib/utils"
import { STATUS } from "@/lib/design-system"
import { useAuth } from "@/lib/auth-context"
import { agentsApi, trainingApi } from "@/lib/api"
import type { Agent, CustomInstruction } from "@/types/api"
import { useAgentKnowledge, type AgentKnowledgeTab } from "@/components/agents/knowledge/use-agent-knowledge"
import { AgentKnowledgeSourcesTab } from "@/components/agents/knowledge/agent-knowledge-sources-tab"
import { AgentKnowledgeExpertPacksTab } from "@/components/agents/knowledge/agent-knowledge-expert-packs-tab"
import { AgentKnowledgeRetrievalTab } from "@/components/agents/knowledge/agent-knowledge-retrieval-tab"
import { AgentKnowledgeAddSheet } from "@/components/agents/knowledge/agent-knowledge-add-sheet"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

const TABS: { id: AgentKnowledgeTab; label: string }[] = [
  { id: "sources", label: "Sources" },
  { id: "expert-packs", label: "Expert Packs" },
  { id: "instructions", label: "Instructions" },
  { id: "retrieval", label: "Retrieval" },
]

function AgentKnowledgePageBody({ agentId }: { agentId: string }) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user } = useAuth()
  const tabParam = searchParams.get("tab") as AgentKnowledgeTab | null
  const [activeTab, setActiveTab] = useState<AgentKnowledgeTab>(
    tabParam && TABS.some((t) => t.id === tabParam) ? tabParam : "sources",
  )
  const [addOpen, setAddOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [itemToDelete, setItemToDelete] = useState<{ id: string; name: string } | null>(null)
  const [mutatingId, setMutatingId] = useState<string | null>(null)

  useEffect(() => {
    if (tabParam && TABS.some((t) => t.id === tabParam)) {
      setActiveTab(tabParam)
    }
  }, [tabParam])

  function selectTab(tab: AgentKnowledgeTab) {
    setActiveTab(tab)
    router.replace(`/agents/${agentId}/knowledge?tab=${tab}`, { scroll: false })
  }

  const { data: agent, isLoading: agentLoading } = useSWR(
    user && agentId ? `agent/${agentId}` : null,
    () => agentsApi.get(agentId),
    { revalidateOnFocus: false },
  )

  const workspace = useAgentKnowledge(agentId, agent?.name ?? "Agent", agent?.department)

  const { data: instructionsData, mutate: mutateInstructions } = useSWR(
    user ? `agent/${agentId}/instructions` : null,
    () => trainingApi.listInstructions(),
    { fallbackData: { instructions: [] as CustomInstruction[] } },
  )
  const instructions = instructionsData?.instructions ?? []

  const kpiTone = useMemo(() => {
    const health = workspace.summary.healthLabel.toLowerCase()
    if (health === "fresh" || health === "ready") return "emerald"
    if (health === "stale") return "amber"
    if (health === "failed" || health === "expired") return "red"
    return "neutral"
  }, [workspace.summary.healthLabel])

  async function handleToggleInstruction(instruction: CustomInstruction) {
    try {
      setMutatingId(instruction.id)
      await trainingApi.updateInstruction(instruction.id, { is_active: !instruction.is_active })
      toast.success(instruction.is_active ? "Instruction deactivated" : "Instruction activated")
      await mutateInstructions()
    } catch {
      toast.error("Failed to update instruction")
    } finally {
      setMutatingId(null)
    }
  }

  async function confirmDelete() {
    if (!itemToDelete) return
    try {
      setMutatingId(itemToDelete.id)
      await trainingApi.deleteInstruction(itemToDelete.id)
      toast.success("Instruction deleted")
      await mutateInstructions()
    } catch {
      toast.error("Failed to delete instruction")
    } finally {
      setMutatingId(null)
      setItemToDelete(null)
      setDeleteDialogOpen(false)
    }
  }

  if (agentLoading && !agent) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  if (!agent) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
        <p className="text-sm text-muted-foreground">Agent not found or you don&apos;t have access.</p>
        <Link href="/agents">
          <Button variant="outline" size="sm">
            Back to AI Team
          </Button>
        </Link>
      </div>
    )
  }

  return (
    <>
      <GravitrePageHeader
        eyebrow="AI Team"
        title="Knowledge"
        description={`Ground and continuously improve ${agent.name} with company knowledge, expert intelligence and connected sources.`}
        icon={<NavDatabase className="h-5 w-5" />}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="outline" size="sm" asChild>
              <Link href="/sources">Manage library</Link>
            </Button>
            <Button type="button" size="sm" className="gap-1.5" onClick={() => setAddOpen(true)}>
              <Icon name="add" size="sm" />
              Add knowledge
            </Button>
          </div>
        }
      />

      <section className="mb-6 grid grid-cols-2 gap-[var(--np-kpi-gap)] lg:grid-cols-4">
        <GravitreMetric label="Sources" value={workspace.summary.sourceCount} hint="Assigned to this agent" />
        <GravitreMetric label="Indexed" value={workspace.summary.indexedLabel} hint="Connected knowledge surfaces" />
        <GravitreMetric
          label="Knowledge health"
          value={workspace.summary.healthLabel}
          className={kpiTone === "emerald" ? "text-emerald-600" : undefined}
        />
        <GravitreMetric label="Last sync" value={workspace.summary.lastSyncLabel} />
      </section>

      <div className="relative mb-6 flex w-fit flex-wrap items-center gap-1 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-2)] p-1">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => selectTab(tab.id)}
            className={cn(
              "relative z-10 rounded-[var(--np-radius-md)] px-4 py-2 text-sm font-medium transition-colors",
              activeTab === tab.id ? "text-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {activeTab === tab.id ? (
              <motion.span
                layoutId="agent-knowledge-tab"
                className="absolute inset-0 rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-1)] shadow-[var(--np-shadow)]"
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
              />
            ) : null}
            <span className="relative">{tab.label}</span>
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2 }}
        >
          {activeTab === "sources" ? (
            <AgentKnowledgeSourcesTab workspace={workspace} agentId={agentId} agentName={agent.name} />
          ) : null}
          {activeTab === "expert-packs" ? (
            <AgentKnowledgeExpertPacksTab workspace={workspace} agentCapabilities={agent.capabilities} />
          ) : null}
          {activeTab === "instructions" ? (
            <div className="space-y-3">
              {instructions.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No custom instructions yet.{" "}
                  <Link href="/training" className="underline underline-offset-2">
                    Add instructions in Training
                  </Link>
                  .
                </p>
              ) : (
                instructions.map((instruction) => (
                  <div
                    key={instruction.id}
                    className="flex items-center gap-4 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium">{instruction.name}</h4>
                        {instruction.is_active ? (
                          <span className={cn("rounded border px-2 py-0.5 text-[10px] uppercase", STATUS.verified)}>
                            Active
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{instruction.content}</p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={mutatingId === instruction.id}
                        onClick={() => void handleToggleInstruction(instruction)}
                      >
                        {instruction.is_active ? "Deactivate" : "Activate"}
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={mutatingId === instruction.id}
                        onClick={() => {
                          setItemToDelete({ id: instruction.id, name: instruction.name })
                          setDeleteDialogOpen(true)
                        }}
                      >
                        Delete
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
          ) : null}
          {activeTab === "retrieval" ? <AgentKnowledgeRetrievalTab agentId={agentId} /> : null}
        </motion.div>
      </AnimatePresence>

      <AgentKnowledgeAddSheet
        open={addOpen}
        onOpenChange={setAddOpen}
        onBrowseExpertPacks={() => selectTab("expert-packs")}
      />

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete instruction?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete &quot;{itemToDelete?.name}&quot;.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => void confirmDelete()}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

export default function AgentKnowledgePage({ params }: { params: Promise<{ id: string }> }) {
  const { id: agentId } = use(params)

  return (
    <AppShell title="Knowledge">
      <div className="flex h-full min-h-0 w-full flex-col bg-[color:var(--g-canvas)] px-[var(--np-page-pad-sm)] py-6 sm:px-[var(--np-page-pad)]">
        <Suspense fallback={<Spinner size="lg" className="mx-auto mt-20" />}>
          <AgentKnowledgePageBody agentId={agentId} />
        </Suspense>
      </div>
    </AppShell>
  )
}
