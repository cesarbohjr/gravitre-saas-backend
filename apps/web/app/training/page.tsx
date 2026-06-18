"use client"

import { useMemo, useState, useEffect, Suspense } from "react"
import useSWR from "swr"
import { useSearchParams } from "next/navigation"
import Link from "next/link"
import { AnimatePresence, motion } from "framer-motion"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { DataFreshness } from "@/components/gravitre/data-freshness"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import { trainingApi, agentsApi } from "@/lib/api"
import { ensureSelectedOrg } from "@/lib/org-context"
import type {
  CustomInstruction,
  FineTunedModel,
  TrainingDataset,
  TrainingDatasetType,
  TrainingJob,
  WorkflowAgent,
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

function formatTrainingError(error: unknown): string {
  if (!error) return "Failed to load training data."
  const message = error instanceof Error ? error.message : String(error)
  if (/organization context|403/i.test(message)) {
    return "Organization membership required. Select an organization and retry."
  }
  if (/500|schema|migration|does not exist|pgrst/i.test(message)) {
    return "Training storage is not fully provisioned yet. You can still explore the hub; run database migrations if create actions fail."
  }
  return message
}

const BASE_MODEL_OPTIONS = ["gpt-4.1-mini", "gpt-5.5", "meson-base-v1"] as const

const STARTER_EXAMPLES = [
  {
    input: "Monitor overdue invoices and notify finance when totals exceed $10k",
    expected_output:
      "Set weekly AR review, alert finance when overdue total exceeds threshold, and log actions in CRM.",
  },
  {
    input: "Customer asks why sync-customers failed at step 3",
    expected_output:
      "Identify timeout at transformation step, recommend retry with 60s timeout and off-peak schedule.",
  },
] as const

function TrainingPageContent() {
  const searchParams = useSearchParams()
  const agentFilterId = searchParams.get("agentId") ?? ""
  const { user } = useAuth()
  const [orgReady, setOrgReady] = useState(false)
  const [orgError, setOrgError] = useState<string | null>(null)
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
  const [assignAgentId, setAssignAgentId] = useState<string>("")
  const [assignModelId, setAssignModelId] = useState<string>("")
  const [isAssigningModel, setIsAssigningModel] = useState(false)
  const [recordDatasetId, setRecordDatasetId] = useState<string | null>(null)
  const [recordInput, setRecordInput] = useState("")
  const [recordOutput, setRecordOutput] = useState("")
  const [trainDatasetId, setTrainDatasetId] = useState<string | null>(null)
  const [trainModelBase, setTrainModelBase] = useState<string>(BASE_MODEL_OPTIONS[0])
  const [isCreatingStarter, setIsCreatingStarter] = useState(false)

  useEffect(() => {
    if (!user) return
    void ensureSelectedOrg(true).then((orgId) => {
      if (!orgId) {
        setOrgError("Organization membership required to load training data.")
        setOrgReady(false)
        return
      }
      setOrgError(null)
      setOrgReady(true)
    })
  }, [user])

  const swrKey = user && orgReady ? "training" : null

  const { data: datasetsData, error: datasetsError, mutate: mutateDatasets } = useSWR(
    swrKey ? "training/datasets" : null,
    () => trainingApi.listDatasets(),
    { fallbackData: { datasets: [] as TrainingDataset[] }, revalidateOnFocus: false }
  )
  const { data: jobsData, error: jobsError, mutate: mutateJobs } = useSWR(
    swrKey ? "training/jobs" : null,
    () => trainingApi.listJobs(),
    {
      fallbackData: { jobs: [] as TrainingJob[] },
      revalidateOnFocus: false,
      refreshInterval: (latest) => {
        const active = (latest?.jobs ?? []).some(
          (job) => job.status === "queued" || job.status === "training"
        )
        return active ? 5000 : 0
      },
    }
  )
  const { data: instructionsData, error: instructionsError, mutate: mutateInstructions } = useSWR(
    swrKey ? "training/instructions" : null,
    () => trainingApi.listInstructions(),
    { fallbackData: { instructions: [] as CustomInstruction[] }, revalidateOnFocus: false }
  )
  const { data: workflowAgentsData, mutate: mutateWorkflowAgents } = useSWR(
    swrKey ? "training/workflow-agents" : null,
    () => trainingApi.listWorkflowAgents(),
    { fallbackData: { agents: [] as WorkflowAgent[] }, revalidateOnFocus: false }
  )
  const { data: agentsFallbackData } = useSWR(
    swrKey ? "training/agents-fallback" : null,
    async () => {
      const response = await agentsApi.list()
      const raw = response.agents ?? []
      return raw.map(
        (agent): WorkflowAgent => ({
          id: String(agent.id),
          name: String(agent.name ?? "Agent"),
          role: agent.role,
          status: agent.status,
          trainedModelId: null,
        }),
      )
    },
    { revalidateOnFocus: false }
  )
  const { data: fineTunedModelsData } = useSWR(
    swrKey ? "training/fine-tuned-models" : null,
    () => trainingApi.listFineTunedModels(),
    { fallbackData: { models: [] as FineTunedModel[] }, revalidateOnFocus: false }
  )

  const datasets = datasetsData?.datasets ?? []
  const jobs = jobsData?.jobs ?? []
  const instructions = instructionsData?.instructions ?? []
  const workflowAgents = workflowAgentsData?.agents ?? []
  const assignableAgents = useMemo(() => {
    if (workflowAgents.length > 0) return workflowAgents
    return agentsFallbackData ?? []
  }, [workflowAgents, agentsFallbackData])
  const fineTunedModels = fineTunedModelsData?.models ?? []
  const filteredAgent = assignableAgents.find((agent) => agent.id === agentFilterId)
  const visibleInstructions = useMemo(() => {
    if (!agentFilterId) return instructions
    return instructions.filter(
      (instruction) => !instruction.agent_id || instruction.agent_id === agentFilterId,
    )
  }, [instructions, agentFilterId])

  const effectiveSelectedAgentId = selectedAgentId || agentFilterId || assignableAgents[0]?.id || ""
  const effectiveAssignAgentId = assignAgentId || agentFilterId || assignableAgents[0]?.id || ""
  const assignedModelForAgent = assignableAgents.find((a) => a.id === effectiveAssignAgentId)?.trainedModelId
  const effectiveAssignModelId = assignModelId || assignedModelForAgent || fineTunedModels[0]?.id || ""

  const stats = useMemo(() => {
    const readyDatasets = datasets.filter((d) => d.status === "ready").length
    const activeJobs = jobs.filter((j) => j.status === "queued" || j.status === "training").length
    const activeInstructions = instructions.filter((i) => i.is_active).length
    const scopedInstructions = agentFilterId
      ? instructions.filter((i) => !i.agent_id || i.agent_id === agentFilterId).length
      : instructions.length
    return {
      totalDatasets: datasets.length,
      readyDatasets,
      totalJobs: jobs.length,
      activeJobs,
      totalInstructions: scopedInstructions,
      activeInstructions,
    }
  }, [datasets, jobs, instructions, agentFilterId])

  async function handleCreateDataset() {
    if (!datasetName.trim()) return
    try {
      setIsCreatingDataset(true)
      await ensureSelectedOrg(true)
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

  async function handleCreateStarterDataset() {
    try {
      setIsCreatingStarter(true)
      await ensureSelectedOrg(true)
      const created = await trainingApi.createDataset({
        name: "Agent persona starter examples",
        type: "examples",
        description: "Seed examples for revenue ops and sync troubleshooting personas.",
      })
      await trainingApi.uploadRecords(created.id, [...STARTER_EXAMPLES])
      toast.success("Starter dataset created with example records")
      setRecordDatasetId(null)
      await mutateDatasets()
    } catch (error) {
      console.error("[training] Starter dataset failed:", error)
      toast.error("Failed to create starter dataset", {
        description: formatTrainingError(error),
      })
    } finally {
      setIsCreatingStarter(false)
    }
  }

  async function handleAddRecord(datasetId: string) {
    if (!recordInput.trim() || !recordOutput.trim()) {
      toast.error("Input and expected output are required")
      return
    }
    try {
      setMutatingDatasetId(datasetId)
      await ensureSelectedOrg(true)
      await trainingApi.uploadRecords(datasetId, [
        { input: recordInput.trim(), expected_output: recordOutput.trim() },
      ])
      toast.success("Training record added")
      setRecordInput("")
      setRecordOutput("")
      setRecordDatasetId(null)
      await mutateDatasets()
    } catch (error) {
      console.error("[v0] Add record failed:", error)
      toast.error("Failed to add record", { description: formatTrainingError(error) })
    } finally {
      setMutatingDatasetId((current) => (current === datasetId ? null : current))
    }
  }

  async function handleCreateJob(datasetId: string) {
    if (!trainModelBase.trim()) return
    try {
      setMutatingDatasetId(datasetId)
      await ensureSelectedOrg(true)
      await trainingApi.createJob(datasetId, trainModelBase.trim())
      toast.success("Training job queued")
      setTrainDatasetId(null)
      await mutateJobs()
    } catch (error) {
      console.error("[v0] Create job failed:", error)
      toast.error("Failed to queue training job", { description: formatTrainingError(error) })
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
        agent_id: effectiveSelectedAgentId || undefined,
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

  async function handleAssignFineTunedModel() {
    if (!effectiveAssignAgentId) return
    try {
      setIsAssigningModel(true)
      await trainingApi.assignAgentFineTunedModel(
        effectiveAssignAgentId,
        effectiveAssignModelId ? effectiveAssignModelId : null
      )
      toast.success(effectiveAssignModelId ? "Fine-tuned model assigned" : "Fine-tuned model cleared")
      await mutateWorkflowAgents()
    } catch (error) {
      console.error("[v0] Assign fine-tuned model failed:", error)
      toast.error("Failed to assign fine-tuned model")
    } finally {
      setIsAssigningModel(false)
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

  const loadError =
    orgError ??
    (datasetsError ? formatTrainingError(datasetsError) : null) ??
    (jobsError ? formatTrainingError(jobsError) : null) ??
    (instructionsError ? formatTrainingError(instructionsError) : null)

  return (
    <AppShell title="Training Hub">
      <div className="relative p-6 space-y-6 overflow-hidden">
        <div className="pointer-events-none absolute -top-24 -left-24 h-64 w-64 rounded-full bg-emerald-500/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 -right-24 h-64 w-64 rounded-full bg-blue-500/10 blur-3xl" />
        {loadError && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span>{loadError}</span>
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs"
              onClick={() => {
                void ensureSelectedOrg(true).then((orgId) => {
                  setOrgReady(Boolean(orgId))
                  setOrgError(orgId ? null : "Organization membership required to load training data.")
                })
                void mutateDatasets()
                void mutateJobs()
                void mutateInstructions()
                void mutateWorkflowAgents()
              }}
            >
              Retry
            </Button>
          </div>
        )}

        {agentFilterId && filteredAgent ? (
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-sm flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span className="text-muted-foreground">
              Training knowledge for <span className="font-medium text-foreground">{filteredAgent.name}</span>
            </span>
            <div className="flex gap-2">
              <Button asChild variant="outline" size="sm" className="h-8">
                <Link href={`/agents/${agentFilterId}/knowledge`}>RAG sources</Link>
              </Button>
              <Button asChild variant="ghost" size="sm" className="h-8">
                <Link href="/training">Clear filter</Link>
              </Button>
            </div>
          </div>
        ) : null}

        {!loadError && orgReady && datasets.length === 0 && jobs.length === 0 && instructions.length === 0 ? (
          <div className="rounded-lg border border-border bg-card/60 px-4 py-3 text-sm text-muted-foreground flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <span>No training datasets, jobs, or instructions yet. Create a dataset below or load starter examples.</span>
            <Button
              size="sm"
              variant="outline"
              disabled={isCreatingStarter}
              onClick={() => void handleCreateStarterDataset()}
            >
              {isCreatingStarter ? "Creating..." : "Load starter examples"}
            </Button>
          </div>
        ) : null}

        <div className="relative grid grid-cols-2 md:grid-cols-6 gap-3">
          <div className="col-span-2 md:col-span-6 flex justify-end">
            <DataFreshness
              updatedAt={datasetsData || jobsData ? Date.now() : null}
              onRefresh={() => {
                void mutateDatasets()
                void mutateJobs()
                void mutateInstructions()
              }}
            />
          </div>
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
                  {recordDatasetId === dataset.id && (
                    <div className="mt-3 grid grid-cols-1 gap-2 rounded-lg border border-border/60 bg-background/50 p-3">
                      <textarea
                        value={recordInput}
                        onChange={(event) => setRecordInput(event.target.value)}
                        placeholder="Training input"
                        className="min-h-16 rounded-lg border border-border bg-background/80 px-3 py-2 text-sm"
                      />
                      <textarea
                        value={recordOutput}
                        onChange={(event) => setRecordOutput(event.target.value)}
                        placeholder="Expected output"
                        className="min-h-16 rounded-lg border border-border bg-background/80 px-3 py-2 text-sm"
                      />
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => void handleAddRecord(dataset.id)} disabled={mutatingDatasetId === dataset.id}>
                          Save record
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setRecordDatasetId(null)}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}
                  {trainDatasetId === dataset.id && (
                    <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-border/60 bg-background/50 p-3">
                      <select
                        value={trainModelBase}
                        onChange={(event) => setTrainModelBase(event.target.value)}
                        className="rounded-lg border border-border bg-background/80 px-3 py-2 text-sm"
                      >
                        {BASE_MODEL_OPTIONS.map((model) => (
                          <option key={model} value={model}>
                            {model}
                          </option>
                        ))}
                      </select>
                      <Button size="sm" onClick={() => void handleCreateJob(dataset.id)} disabled={mutatingDatasetId === dataset.id}>
                        Queue job
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setTrainDatasetId(null)}>
                        Cancel
                      </Button>
                    </div>
                  )}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="hover:border-emerald-500/40 hover:text-emerald-400"
                      disabled={mutatingDatasetId === dataset.id}
                      onClick={() => {
                        setTrainDatasetId(null)
                        setRecordDatasetId(recordDatasetId === dataset.id ? null : dataset.id)
                        setRecordInput("")
                        setRecordOutput("")
                      }}
                    >
                      Add Record
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="hover:border-blue-500/40 hover:text-blue-400"
                      disabled={mutatingDatasetId === dataset.id || dataset.record_count < 1}
                      onClick={() => {
                        setRecordDatasetId(null)
                        setTrainDatasetId(trainDatasetId === dataset.id ? null : dataset.id)
                      }}
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
                      className="relative h-full bg-gradient-to-r from-blue-500 to-cyan-400 overflow-hidden"
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.max(0, Math.min(100, job.progress))}%` }}
                      transition={{ duration: 0.45, ease: "easeOut" }}
                    >
                      {(job.status === "training" || job.status === "queued") && (
                        <motion.span
                          aria-hidden="true"
                          className="absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-white/40 to-transparent"
                          animate={{ x: ["-120%", "320%"] }}
                          transition={{ duration: 1.3, repeat: Infinity, ease: "easeInOut" }}
                        />
                      )}
                    </motion.div>
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
              value={effectiveSelectedAgentId}
              onChange={(event) => setSelectedAgentId(event.target.value)}
              className="rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
            >
              <option value="">All agents</option>
              {assignableAgents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                  {agent.role ? ` · ${agent.role}` : ""}
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
              {visibleInstructions.map((instruction) => (
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
            {visibleInstructions.length === 0 && (
              <p className="text-sm text-muted-foreground">
                {agentFilterId ? "No custom instructions for this agent yet." : "No custom instructions yet."}
              </p>
            )}
          </div>
        </motion.section>

        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.24 }}
          className="rounded-2xl border border-border bg-card/80 backdrop-blur-sm p-5 space-y-4 shadow-sm"
        >
          <h2 className="text-lg font-semibold text-foreground">Agent Fine-Tuned Models</h2>
          <p className="text-sm text-muted-foreground">
            Assign a deployable fine-tuned model to a workflow agent. Inference falls back to the agent base model on provider failure.
          </p>
          <div className="grid grid-cols-1 gap-2 rounded-xl border border-border/50 bg-background/40 p-3 md:grid-cols-2">
            <select
              value={effectiveAssignAgentId}
              onChange={(event) => {
                setAssignAgentId(event.target.value)
                setAssignModelId("")
              }}
              className="rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
            >
              {assignableAgents.length === 0 && <option value="">No workflow agents</option>}
              {assignableAgents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name} {agent.model ? `(${agent.model})` : ""}
                </option>
              ))}
            </select>
            <select
              value={effectiveAssignModelId}
              onChange={(event) => setAssignModelId(event.target.value)}
              className="rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
            >
              <option value="">Base model only (clear assignment)</option>
              {fineTunedModels.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name} · v{model.deployedVersion ?? model.currentVersion ?? "?"} · {model.status}
                </option>
              ))}
            </select>
            <Button
              className="md:col-span-2 bg-gradient-to-r from-emerald-500 to-teal-500 text-white hover:from-emerald-600 hover:to-teal-600"
              onClick={() => void handleAssignFineTunedModel()}
              disabled={isAssigningModel || !effectiveAssignAgentId}
            >
              {isAssigningModel ? "Saving..." : "Save Assignment"}
            </Button>
          </div>
          {fineTunedModels.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No deployable fine-tuned models yet. Complete a fine-tuning job first.
            </p>
          )}
          {assignableAgents.some((a) => a.trainedModelId) && (
            <div className="space-y-2">
              {assignableAgents
                .filter((a) => a.trainedModelId)
                .map((agent) => {
                  const model = fineTunedModels.find((m) => m.id === agent.trainedModelId)
                  return (
                    <div key={agent.id} className="rounded-xl border border-border p-3 bg-background/40 text-sm">
                      <span className="font-medium text-foreground">{agent.name}</span>
                      <span className="text-muted-foreground">
                        {" "}
                        → {model?.name ?? agent.trainedModelId}
                        {model?.fineTunedOpenAiId ? ` (${model.fineTunedOpenAiId})` : ""}
                      </span>
                    </div>
                  )
                })}
            </div>
          )}
        </motion.section>
      </div>
    </AppShell>
  )
}

export default function TrainingPage() {
  return (
    <Suspense
      fallback={
        <AppShell title="Training Hub">
          <div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">
            Loading training hub…
          </div>
        </AppShell>
      }
    >
      <TrainingPageContent />
    </Suspense>
  )
}
