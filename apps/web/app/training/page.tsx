"use client"

import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import { AnimatePresence, motion } from "framer-motion"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import { agentsApi, trainingApi } from "@/lib/api"
import type {
  Agent,
  CustomInstruction,
  TrainingDataset,
  TrainingDatasetType,
  TrainingJob,
} from "@/types/api"
import { cn } from "@/lib/utils"

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
  return parsed.toLocaleString()
}

export default function TrainingPage() {
  const { user } = useAuth()
  const [datasetName, setDatasetName] = useState("")
  const [datasetDescription, setDatasetDescription] = useState("")
  const [datasetType, setDatasetType] = useState<TrainingDatasetType>("examples")
  const [instructionName, setInstructionName] = useState("")
  const [instructionContent, setInstructionContent] = useState("")
  const [selectedAgentId, setSelectedAgentId] = useState<string>("")
  const [isCreatingDataset, setIsCreatingDataset] = useState(false)
  const [isCreatingInstruction, setIsCreatingInstruction] = useState(false)
  const [mutatingDatasetId, setMutatingDatasetId] = useState<string | null>(null)
  const [mutatingJobId, setMutatingJobId] = useState<string | null>(null)
  const [mutatingInstructionId, setMutatingInstructionId] = useState<string | null>(null)

  const { data: datasetsData, error: datasetsError, mutate: mutateDatasets } = useSWR(
    user ? "training/datasets" : null,
    () => trainingApi.listDatasets(),
    { fallbackData: { datasets: [] as TrainingDataset[] }, revalidateOnFocus: false }
  )
  const { data: jobsData, error: jobsError, mutate: mutateJobs } = useSWR(
    user ? "training/jobs" : null,
    () => trainingApi.listJobs(),
    { fallbackData: { jobs: [] as TrainingJob[] }, revalidateOnFocus: false }
  )
  const { data: instructionsData, error: instructionsError, mutate: mutateInstructions } = useSWR(
    user ? "training/instructions" : null,
    () => trainingApi.listInstructions(),
    { fallbackData: { instructions: [] as CustomInstruction[] }, revalidateOnFocus: false }
  )
  const { data: agentsData } = useSWR(
    user ? "training/agents" : null,
    () => agentsApi.list(),
    { fallbackData: { agents: [] as Agent[] }, revalidateOnFocus: false }
  )

  const datasets = datasetsData?.datasets ?? []
  const jobs = jobsData?.jobs ?? []
  const instructions = instructionsData?.instructions ?? []
  const agents = agentsData?.agents ?? []

  useEffect(() => {
    if (!selectedAgentId && agents.length > 0) {
      setSelectedAgentId(agents[0].id)
    }
  }, [agents, selectedAgentId])

  const stats = useMemo(() => {
    const readyDatasets = datasets.filter((d) => d.status === "ready").length
    const activeJobs = jobs.filter((j) => j.status === "queued" || j.status === "training").length
    const activeInstructions = instructions.filter((i) => i.is_active).length
    return {
      totalDatasets: datasets.length,
      readyDatasets,
      totalJobs: jobs.length,
      activeJobs,
      totalInstructions: instructions.length,
      activeInstructions,
    }
  }, [datasets, jobs, instructions])

  async function handleCreateDataset() {
    if (!datasetName.trim()) return
    try {
      setIsCreatingDataset(true)
      await trainingApi.createDataset({
        name: datasetName.trim(),
        type: datasetType,
        description: datasetDescription.trim() || undefined,
      })
      toast.success("Dataset created")
      setDatasetName("")
      setDatasetDescription("")
      setDatasetType("examples")
      await mutateDatasets()
    } catch (error) {
      console.error("[v0] Create dataset failed:", error)
      toast.error("Failed to create dataset")
    } finally {
      setIsCreatingDataset(false)
    }
  }

  async function handleDeleteDataset(datasetId: string) {
    if (!window.confirm("Delete this dataset?")) return
    try {
      setMutatingDatasetId(datasetId)
      await trainingApi.deleteDataset(datasetId)
      toast.success("Dataset deleted")
      await Promise.all([mutateDatasets(), mutateJobs()])
    } catch (error) {
      console.error("[v0] Delete dataset failed:", error)
      toast.error("Failed to delete dataset")
    } finally {
      setMutatingDatasetId((current) => (current === datasetId ? null : current))
    }
  }

  async function handleAddRecord(datasetId: string) {
    const input = window.prompt("Training input")
    if (!input?.trim()) return
    const expectedOutput = window.prompt("Expected output")
    if (!expectedOutput?.trim()) return
    try {
      setMutatingDatasetId(datasetId)
      await trainingApi.uploadRecords(datasetId, [{ input: input.trim(), expected_output: expectedOutput.trim() }])
      toast.success("Training record added")
      await mutateDatasets()
    } catch (error) {
      console.error("[v0] Add record failed:", error)
      toast.error("Failed to add record")
    } finally {
      setMutatingDatasetId((current) => (current === datasetId ? null : current))
    }
  }

  async function handleCreateJob(datasetId: string) {
    const modelBase = window.prompt("Base model", "meson-base-v1")?.trim()
    if (!modelBase) return
    try {
      setMutatingDatasetId(datasetId)
      await trainingApi.createJob(datasetId, modelBase)
      toast.success("Training job queued")
      await mutateJobs()
    } catch (error) {
      console.error("[v0] Create job failed:", error)
      toast.error("Failed to queue training job")
    } finally {
      setMutatingDatasetId((current) => (current === datasetId ? null : current))
    }
  }

  async function handleCancelJob(jobId: string) {
    try {
      setMutatingJobId(jobId)
      await trainingApi.cancelJob(jobId)
      toast.success("Training job cancelled")
      await mutateJobs()
    } catch (error) {
      console.error("[v0] Cancel job failed:", error)
      toast.error("Failed to cancel job")
    } finally {
      setMutatingJobId((current) => (current === jobId ? null : current))
    }
  }

  async function handleCreateInstruction() {
    if (!instructionName.trim() || !instructionContent.trim()) return
    try {
      setIsCreatingInstruction(true)
      await trainingApi.createInstruction({
        name: instructionName.trim(),
        content: instructionContent.trim(),
        agent_id: selectedAgentId || undefined,
      })
      toast.success("Instruction created")
      setInstructionName("")
      setInstructionContent("")
      await mutateInstructions()
    } catch (error) {
      console.error("[v0] Create instruction failed:", error)
      toast.error("Failed to create instruction")
    } finally {
      setIsCreatingInstruction(false)
    }
  }

  async function handleToggleInstruction(instruction: CustomInstruction) {
    try {
      setMutatingInstructionId(instruction.id)
      await trainingApi.toggleInstruction(instruction.id, !instruction.is_active)
      toast.success(instruction.is_active ? "Instruction disabled" : "Instruction enabled")
      await mutateInstructions()
    } catch (error) {
      console.error("[v0] Toggle instruction failed:", error)
      toast.error("Failed to update instruction")
    } finally {
      setMutatingInstructionId((current) => (current === instruction.id ? null : current))
    }
  }

  async function handleDeleteInstruction(instructionId: string) {
    if (!window.confirm("Delete this instruction?")) return
    try {
      setMutatingInstructionId(instructionId)
      await trainingApi.deleteInstruction(instructionId)
      toast.success("Instruction deleted")
      await mutateInstructions()
    } catch (error) {
      console.error("[v0] Delete instruction failed:", error)
      toast.error("Failed to delete instruction")
    } finally {
      setMutatingInstructionId((current) => (current === instructionId ? null : current))
    }
  }

  return (
    <AppShell title="Training Hub">
      <div className="relative p-6 space-y-6 overflow-hidden">
        <div className="pointer-events-none absolute -top-24 -left-24 h-64 w-64 rounded-full bg-emerald-500/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 -right-24 h-64 w-64 rounded-full bg-blue-500/10 blur-3xl" />
        {(datasetsError || jobsError || instructionsError) && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
            Failed to load some training data. Retry or refresh.
          </div>
        )}

        <div className="relative grid grid-cols-2 md:grid-cols-6 gap-3">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0 }}
            className="rounded-xl border border-border bg-card/80 backdrop-blur-sm p-3 shadow-sm"
          >
            <p className="text-xs text-muted-foreground">Datasets</p>
            <p className="text-xl font-semibold text-foreground">{stats.totalDatasets}</p>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.04 }}
            className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3 shadow-sm"
          >
            <p className="text-xs text-muted-foreground">Ready</p>
            <p className="text-xl font-semibold text-emerald-400">{stats.readyDatasets}</p>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 }}
            className="rounded-xl border border-border bg-card/80 backdrop-blur-sm p-3 shadow-sm"
          >
            <p className="text-xs text-muted-foreground">Jobs</p>
            <p className="text-xl font-semibold text-foreground">{stats.totalJobs}</p>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.12 }}
            className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-3 shadow-sm"
          >
            <p className="text-xs text-muted-foreground">Active Jobs</p>
            <p className="text-xl font-semibold text-blue-400">{stats.activeJobs}</p>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.16 }}
            className="rounded-xl border border-border bg-card/80 backdrop-blur-sm p-3 shadow-sm"
          >
            <p className="text-xs text-muted-foreground">Instructions</p>
            <p className="text-xl font-semibold text-foreground">{stats.totalInstructions}</p>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3 shadow-sm"
          >
            <p className="text-xs text-muted-foreground">Active</p>
            <p className="text-xl font-semibold text-emerald-400">{stats.activeInstructions}</p>
          </motion.div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <motion.section
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 }}
            className="rounded-2xl border border-border bg-card/80 backdrop-blur-sm p-5 space-y-4 shadow-sm"
          >
            <h2 className="text-lg font-semibold text-foreground">Training Datasets</h2>
            <div className="grid grid-cols-1 gap-2 rounded-xl border border-border/50 bg-background/40 p-3">
              <input
                value={datasetName}
                onChange={(event) => setDatasetName(event.target.value)}
                placeholder="Dataset name"
                className="rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
              />
              <select
                value={datasetType}
                onChange={(event) => setDatasetType(event.target.value as TrainingDatasetType)}
                className="rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
              >
                <option value="examples">Examples</option>
                <option value="documents">Documents</option>
                <option value="feedback">Feedback</option>
              </select>
              <textarea
                value={datasetDescription}
                onChange={(event) => setDatasetDescription(event.target.value)}
                placeholder="Description (optional)"
                className="min-h-20 rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
              />
              <Button
                className="bg-gradient-to-r from-emerald-500 to-teal-500 text-white hover:from-emerald-600 hover:to-teal-600"
                onClick={() => void handleCreateDataset()}
                disabled={isCreatingDataset || !datasetName.trim()}
              >
                {isCreatingDataset ? "Creating..." : "Create Dataset"}
              </Button>
            </div>

            <div className="space-y-2">
              <AnimatePresence initial={false}>
                {datasets.map((dataset) => (
                  <motion.div
                    key={dataset.id}
                    layout
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.18 }}
                    className="rounded-xl border border-border p-3 bg-background/40 hover:bg-background/70 transition-colors"
                  >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium text-foreground">{dataset.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {dataset.type} · {dataset.record_count} records · created {formatDate(dataset.created_at)}
                      </p>
                    </div>
                    <span className={cn("rounded-full border px-2 py-0.5 text-[10px] uppercase", statusClasses(dataset.status))}>
                      {dataset.status}
                    </span>
                  </div>
                  {dataset.description && <p className="mt-2 text-xs text-muted-foreground">{dataset.description}</p>}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="hover:border-emerald-500/40 hover:text-emerald-400"
                      disabled={mutatingDatasetId === dataset.id}
                      onClick={() => void handleAddRecord(dataset.id)}
                    >
                      Add Record
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="hover:border-blue-500/40 hover:text-blue-400"
                      disabled={mutatingDatasetId === dataset.id}
                      onClick={() => void handleCreateJob(dataset.id)}
                    >
                      Train
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="hover:border-red-500/40 hover:text-red-400"
                      disabled={mutatingDatasetId === dataset.id}
                      onClick={() => void handleDeleteDataset(dataset.id)}
                    >
                      Delete
                    </Button>
                  </div>
                  </motion.div>
                ))}
              </AnimatePresence>
              {datasets.length === 0 && <p className="text-sm text-muted-foreground">No datasets yet.</p>}
            </div>
          </motion.section>

          <motion.section
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.14 }}
            className="rounded-2xl border border-border bg-card/80 backdrop-blur-sm p-5 space-y-4 shadow-sm"
          >
            <h2 className="text-lg font-semibold text-foreground">Training Jobs</h2>
            <div className="space-y-2">
              <AnimatePresence initial={false}>
                {jobs.map((job) => (
                  <motion.div
                    key={job.id}
                    layout
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.18 }}
                    className="rounded-xl border border-border p-3 bg-background/40 hover:bg-background/70 transition-colors"
                  >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium text-foreground">Dataset {job.dataset_id.slice(0, 8)} · {job.model_base}</p>
                      <p className="text-xs text-muted-foreground">
                        Created {formatDate(job.created_at)} · Progress {job.progress}%
                      </p>
                    </div>
                    <span className={cn("rounded-full border px-2 py-0.5 text-[10px] uppercase", statusClasses(job.status))}>
                      {job.status}
                    </span>
                  </div>
                  <div className="mt-3 h-1.5 rounded-full bg-secondary overflow-hidden">
                    <motion.div
                      className="h-full bg-gradient-to-r from-blue-500 to-cyan-400"
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.max(0, Math.min(100, job.progress))}%` }}
                      transition={{ duration: 0.45, ease: "easeOut" }}
                    />
                  </div>
                  <div className="mt-3 flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="hover:border-red-500/40 hover:text-red-400"
                      disabled={mutatingJobId === job.id || (job.status !== "queued" && job.status !== "training")}
                      onClick={() => void handleCancelJob(job.id)}
                    >
                      Cancel
                    </Button>
                  </div>
                  </motion.div>
                ))}
              </AnimatePresence>
              {jobs.length === 0 && <p className="text-sm text-muted-foreground">No training jobs yet.</p>}
            </div>
          </motion.section>
        </div>

        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="rounded-2xl border border-border bg-card/80 backdrop-blur-sm p-5 space-y-4 shadow-sm"
        >
          <h2 className="text-lg font-semibold text-foreground">Custom Instructions</h2>
          <div className="grid grid-cols-1 gap-2 rounded-xl border border-border/50 bg-background/40 p-3">
            <input
              value={instructionName}
              onChange={(event) => setInstructionName(event.target.value)}
              placeholder="Instruction name"
              className="rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
            />
            <select
              value={selectedAgentId}
              onChange={(event) => setSelectedAgentId(event.target.value)}
              className="rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
            >
              <option value="">All agents</option>
              {agents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                </option>
              ))}
            </select>
            <textarea
              value={instructionContent}
              onChange={(event) => setInstructionContent(event.target.value)}
              placeholder="Instruction content"
              className="min-h-24 rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
            />
            <Button
              className="bg-gradient-to-r from-emerald-500 to-teal-500 text-white hover:from-emerald-600 hover:to-teal-600"
              onClick={() => void handleCreateInstruction()}
              disabled={isCreatingInstruction || !instructionName.trim() || !instructionContent.trim()}
            >
              {isCreatingInstruction ? "Creating..." : "Create Instruction"}
            </Button>
          </div>

          <div className="space-y-2">
            <AnimatePresence initial={false}>
              {instructions.map((instruction) => (
                <motion.div
                  key={instruction.id}
                  layout
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.18 }}
                  className="rounded-xl border border-border p-3 bg-background/40 hover:bg-background/70 transition-colors"
                >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-foreground">{instruction.name}</p>
                    <p className="text-xs text-muted-foreground">
                      Agent: {instruction.agent_name ?? instruction.agent_id ?? "All"} · Updated {formatDate(instruction.updated_at || instruction.created_at)}
                    </p>
                  </div>
                  <span
                    className={cn(
                      "rounded-full border px-2 py-0.5 text-[10px] uppercase",
                      instruction.is_active
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                        : "bg-secondary text-muted-foreground border-border"
                    )}
                  >
                    {instruction.is_active ? "active" : "inactive"}
                  </span>
                </div>
                <p className="mt-2 text-sm text-muted-foreground whitespace-pre-wrap">{instruction.content}</p>
                <div className="mt-3 flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="hover:border-blue-500/40 hover:text-blue-400"
                    disabled={mutatingInstructionId === instruction.id}
                    onClick={() => void handleToggleInstruction(instruction)}
                  >
                    {instruction.is_active ? "Disable" : "Enable"}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="hover:border-red-500/40 hover:text-red-400"
                    disabled={mutatingInstructionId === instruction.id}
                    onClick={() => void handleDeleteInstruction(instruction.id)}
                  >
                    Delete
                  </Button>
                </div>
                </motion.div>
              ))}
            </AnimatePresence>
            {instructions.length === 0 && <p className="text-sm text-muted-foreground">No custom instructions yet.</p>}
          </div>
        </motion.section>
      </div>
    </AppShell>
  )
}
