"use client"

import { useState, use, useMemo, useEffect } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import useSWR from "swr"
import { toast } from "sonner"
import { Loader2 } from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Icon, type IconName } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"
import { agentsApi, trainingApi } from "@/lib/api"
import { AgentReferenceFoldersPanel } from "@/components/agents/agent-reference-folders-panel"
import { AgentReferenceFoldersEditor } from "@/components/agents/agent-reference-folders-editor"
import type { Agent, AgentReferenceFolder, TrainingDataset, CustomInstruction } from "@/types/api"
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

function statusClasses(status: string): string {
  if (status === "ready" || status === "completed") {
    return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
  }
  if (status === "training" || status === "processing" || status === "queued") {
    return "bg-blue-500/10 text-blue-400 border-blue-500/20"
  }
  if (status === "failed") {
    return "bg-red-500/10 text-red-400 border-red-500/20"
  }
  return "bg-secondary text-muted-foreground border-border"
}

function formatDate(value?: string): string {
  if (!value) return "N/A"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return "N/A"
  return parsed.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
}

// Mock agent data removed — load via agentsApi.get (STA-163)

export default function AgentKnowledgePage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id: agentId } = use(params)
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState<"datasets" | "instructions" | "folders">("datasets")
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [itemToDelete, setItemToDelete] = useState<{ type: "dataset" | "instruction"; id: string; name: string } | null>(null)
  const [mutatingId, setMutatingId] = useState<string | null>(null)
  const [folderDraft, setFolderDraft] = useState<AgentReferenceFolder[]>([])
  const [savingFolders, setSavingFolders] = useState(false)

  // Fetch agent data
  const { data: agentData, isLoading: agentLoading, mutate: mutateAgent } = useSWR(
    user && agentId ? `agent/${agentId}` : null,
    () => agentsApi.get(agentId),
    { revalidateOnFocus: false },
  )
  const agent = agentData

  useEffect(() => {
    setFolderDraft(agent?.referenceFolders ?? [])
  }, [agent?.referenceFolders])

  // Fetch datasets
  const { data: datasetsData, mutate: mutateDatasets } = useSWR(
    user ? `agent/${agentId}/datasets` : null,
    () => trainingApi.listDatasets(),
    { fallbackData: { datasets: [] as TrainingDataset[] } }
  )
  // Filter datasets - in a real app, this would filter by agent_id in the API
  const datasets = datasetsData?.datasets ?? []

  // Fetch instructions
  const { data: instructionsData, mutate: mutateInstructions } = useSWR(
    user ? `agent/${agentId}/instructions` : null,
    () => trainingApi.listInstructions(),
    { fallbackData: { instructions: [] as CustomInstruction[] } }
  )
  // Filter instructions - in a real app, this would filter by agent_id in the API
  const instructions = instructionsData?.instructions ?? []

  // Stats
  const stats = useMemo(() => ({
    totalDatasets: datasets.length,
    readyDatasets: datasets.filter((d) => d.status === "ready").length,
    totalInstructions: instructions.length,
    activeInstructions: instructions.filter((i) => i.is_active).length,
  }), [datasets, instructions])

  const handleSaveFolders = async () => {
    if (!agent) return
    try {
      setSavingFolders(true)
      await agentsApi.update(agent.id, { referenceFolders: folderDraft } as Partial<Agent>)
      toast.success("Reference folders updated")
      await mutateAgent()
    } catch (error) {
      console.error("[knowledge] Save folders failed:", error)
      toast.error("Failed to save reference folders")
    } finally {
      setSavingFolders(false)
    }
  }

  // Handle delete
  const handleDeleteClick = (type: "dataset" | "instruction", id: string, name: string) => {
    setItemToDelete({ type, id, name })
    setDeleteDialogOpen(true)
  }

  const confirmDelete = async () => {
    if (!itemToDelete) return
    try {
      setMutatingId(itemToDelete.id)
      if (itemToDelete.type === "dataset") {
        await trainingApi.deleteDataset(itemToDelete.id)
        await mutateDatasets()
      } else {
        await trainingApi.deleteInstruction(itemToDelete.id)
        await mutateInstructions()
      }
      toast.success(`${itemToDelete.type === "dataset" ? "Dataset" : "Instruction"} deleted`)
    } catch (error) {
      console.error("[v0] Delete failed:", error)
      toast.error(`Failed to delete ${itemToDelete.type}`)
    } finally {
      setMutatingId(null)
      setItemToDelete(null)
      setDeleteDialogOpen(false)
    }
  }

  // Toggle instruction active state
  const handleToggleInstruction = async (instruction: CustomInstruction) => {
    try {
      setMutatingId(instruction.id)
      await trainingApi.updateInstruction(instruction.id, { is_active: !instruction.is_active })
      toast.success(instruction.is_active ? "Instruction deactivated" : "Instruction activated")
      await mutateInstructions()
    } catch (error) {
      console.error("[v0] Toggle instruction failed:", error)
      toast.error("Failed to update instruction")
    } finally {
      setMutatingId(null)
    }
  }

  if (agentLoading && !agent) {
    return (
      <AppShell title="Knowledge Base">
        <div className="flex h-full items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-emerald-600" />
        </div>
      </AppShell>
    )
  }

  if (!agent) {
    return (
      <AppShell title="Knowledge Base">
        <div className="flex h-full flex-col items-center justify-center gap-3 text-center px-6">
          <p className="text-sm text-muted-foreground">Agent not found or you don&apos;t have access.</p>
          <Link href="/agents">
            <Button variant="outline" size="sm">Back to AI Team</Button>
          </Link>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title={`${agent.name} - Knowledge Base`}>
      <div className="flex flex-col min-h-full">
        {/* Header */}
        <div className="border-b border-border bg-card/50">
          <div className="px-6 py-6">
            {/* Breadcrumb */}
            <div className="flex items-center gap-2 text-sm mb-4">
              <Link
                href="/agents"
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                AI Team
              </Link>
              <span className="text-muted-foreground/50">/</span>
              <Link
                href={`/agents/${agentId}`}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                {agent.name}
              </Link>
              <span className="text-muted-foreground/50">/</span>
              <span className="text-foreground">Knowledge Base</span>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 shadow-lg shadow-emerald-500/20">
                  <Icon name="database" size="md" className="text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-foreground">Knowledge Base</h1>
                  <p className="text-sm text-muted-foreground">
                    Training data and custom instructions for {agent.name}
                  </p>
                </div>
              </div>

              <Link href="/training">
                <Button variant="outline" className="gap-2">
                  <Icon name="add" size="sm" />
                  Add Training Data
                </Button>
              </Link>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-4 gap-4 mt-6">
              {[
                { label: "Datasets", value: stats.totalDatasets, sub: `${stats.readyDatasets} ready`, icon: "database", color: "emerald" },
                { label: "Instructions", value: stats.totalInstructions, sub: `${stats.activeInstructions} active`, icon: "file", color: "blue" },
                { label: "Training Status", value: stats.readyDatasets > 0 ? "Ready" : "Empty", sub: "Knowledge available", icon: "check", color: stats.readyDatasets > 0 ? "emerald" : "amber" },
                { label: "Last Updated", value: datasets[0]?.updated_at ? formatDate(datasets[0].updated_at) : "Never", sub: "Most recent change", icon: "clock", color: "violet" },
              ].map((stat, i) => (
                <motion.div
                  key={stat.label}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="p-4 rounded-xl border border-border bg-card"
                >
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      "h-10 w-10 rounded-lg flex items-center justify-center",
                      stat.color === "emerald" && "bg-emerald-500/10",
                      stat.color === "blue" && "bg-blue-500/10",
                      stat.color === "violet" && "bg-violet-500/10",
                      stat.color === "amber" && "bg-amber-500/10",
                    )}>
                      <Icon 
                        name={stat.icon as IconName} 
                        size="sm" 
                        className={cn(
                          stat.color === "emerald" && "text-emerald-400",
                          stat.color === "blue" && "text-blue-400",
                          stat.color === "violet" && "text-violet-400",
                          stat.color === "amber" && "text-amber-400",
                        )} 
                      />
                    </div>
                    <div>
                      <p className="text-lg font-bold text-foreground">{stat.value}</p>
                      <p className="text-xs text-muted-foreground">{stat.label}</p>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 p-6">
          {/* Tabs */}
          <div className="flex items-center gap-1 p-1 rounded-xl bg-secondary/50 w-fit mb-6">
            {[
              { id: "datasets", label: "Training Datasets", icon: "database" },
              { id: "instructions", label: "Custom Instructions", icon: "file" },
              { id: "folders", label: "Reference Folders", icon: "folder" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all",
                  activeTab === tab.id
                    ? "bg-card text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon name={tab.icon as IconName} size="sm" />
                {tab.label}
              </button>
            ))}
          </div>

          <AnimatePresence mode="wait">
            {activeTab === "datasets" && (
              <motion.div
                key="datasets"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
              >
                {datasets.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <div className="h-16 w-16 rounded-2xl bg-secondary/50 flex items-center justify-center mb-4">
                      <Icon name="database" size="lg" className="text-muted-foreground" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">No Training Data</h3>
                    <p className="text-sm text-muted-foreground mb-6 max-w-md">
                      Add training datasets to improve {agent.name}&apos;s knowledge and capabilities.
                    </p>
                    <Link href="/training">
                      <Button className="gap-2 bg-emerald-600 hover:bg-emerald-500">
                        <Icon name="add" size="sm" />
                        Add Training Data
                      </Button>
                    </Link>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {datasets.map((dataset, i) => (
                      <motion.div
                        key={dataset.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.05 }}
                        className="group flex items-center gap-4 p-4 rounded-xl border border-border bg-card hover:bg-secondary/30 transition-colors"
                      >
                        <div className="h-10 w-10 rounded-lg bg-emerald-500/10 flex items-center justify-center shrink-0">
                          <Icon name="database" size="sm" className="text-emerald-400" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <h4 className="font-medium text-foreground">{dataset.name}</h4>
                            <span className={cn(
                              "px-2 py-0.5 rounded text-[10px] font-medium uppercase border",
                              statusClasses(dataset.status)
                            )}>
                              {dataset.status}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
                            <span>{dataset.type}</span>
                            <span className="text-muted-foreground/50">|</span>
                            <span>{dataset.record_count ?? 0} records</span>
                            <span className="text-muted-foreground/50">|</span>
                            <span>Updated {formatDate(dataset.updated_at)}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteClick("dataset", dataset.id, dataset.name)}
                            disabled={mutatingId === dataset.id}
                            className="text-muted-foreground hover:text-red-400"
                          >
                            <Icon name="trash" size="sm" />
                          </Button>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                )}
              </motion.div>
            )}

            {activeTab === "instructions" && (
              <motion.div
                key="instructions"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
              >
                {instructions.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <div className="h-16 w-16 rounded-2xl bg-secondary/50 flex items-center justify-center mb-4">
                      <Icon name="file" size="lg" className="text-muted-foreground" />
                    </div>
                    <h3 className="text-lg font-semibold text-foreground mb-2">No Custom Instructions</h3>
                    <p className="text-sm text-muted-foreground mb-6 max-w-md">
                      Add custom instructions to guide {agent.name}&apos;s behavior and responses.
                    </p>
                    <Link href="/training">
                      <Button className="gap-2 bg-emerald-600 hover:bg-emerald-500">
                        <Icon name="add" size="sm" />
                        Add Instructions
                      </Button>
                    </Link>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {instructions.map((instruction, i) => (
                      <motion.div
                        key={instruction.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.05 }}
                        className="group flex items-center gap-4 p-4 rounded-xl border border-border bg-card hover:bg-secondary/30 transition-colors"
                      >
                        <div className={cn(
                          "h-10 w-10 rounded-lg flex items-center justify-center shrink-0",
                          instruction.is_active ? "bg-emerald-500/10" : "bg-secondary"
                        )}>
                          <Icon 
                            name="file" 
                            size="sm" 
                            className={instruction.is_active ? "text-emerald-400" : "text-muted-foreground"} 
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <h4 className="font-medium text-foreground">{instruction.name}</h4>
                            {instruction.is_active && (
                              <span className="px-2 py-0.5 rounded text-[10px] font-medium uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                Active
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
                            {instruction.content}
                          </p>
                        </div>
                        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleToggleInstruction(instruction)}
                            disabled={mutatingId === instruction.id}
                            className="text-muted-foreground hover:text-foreground"
                          >
                                                    <Icon name={instruction.is_active ? "close" : "check"} size="sm" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteClick("instruction", instruction.id, instruction.name)}
                            disabled={mutatingId === instruction.id}
                            className="text-muted-foreground hover:text-red-400"
                          >
                            <Icon name="trash" size="sm" />
                          </Button>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                )}
              </motion.div>
            )}

            {activeTab === "folders" && (
              <motion.div
                key="folders"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="space-y-4"
              >
                <AgentReferenceFoldersEditor value={folderDraft} onChange={setFolderDraft} />
                {(agent.referenceFolders ?? []).length > 0 ? (
                  <AgentReferenceFoldersPanel
                    folders={agent.referenceFolders ?? []}
                    title="Currently linked"
                    description="These folder paths are active for this agent."
                    compact
                  />
                ) : null}
                <div className="flex justify-end">
                  <Button onClick={handleSaveFolders} disabled={savingFolders} className="gap-2">
                    {savingFolders ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                    Save folder references
                  </Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {itemToDelete?.type}?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete &quot;{itemToDelete?.name}&quot;. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} className="bg-red-500 hover:bg-red-600">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppShell>
  )
}
