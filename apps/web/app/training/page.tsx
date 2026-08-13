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
import { LearningSurfacesCallout } from "@/components/gravitre/learning-surfaces-callout"
import { AgentsHubTabs } from "@/components/agents/agents-hub-tabs"
import { PageHeader, StatCard, StatsGrid } from "@/components/gravitre/page-header"
import { TrainingOverview } from "@/components/gravitre/training-overview"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { DATASET_TYPE_META, TRAINABLE_BASE_MODELS, datasetTypeMeta } from "@/lib/training-ui-copy"
import { Brain, RefreshCw } from "lucide-react"

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
  if (/Backend unavailable|Could not reach the training backend|Backend request failed|502|503/i.test(message)) {
    return "Could not reach the training backend. If chat works but Training does not, redeploy the web app or verify FASTAPI_BASE_URL on Vercel."
  }
  if (/500|schema|migration|does not exist|pgrst|not provisioned/i.test(message)) {
    return "Training storage is not fully provisioned yet. Apply Supabase migrations for training_datasets, then retry."
  }
  return message
}

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
  const [trainModelBase, setTrainModelBase] = useState<string>(TRAINABLE_BASE_MODELS[0].id)
  const [isCreatingStarter, setIsCreatingStarter] = useState(false)
  const [bulkText, setBulkText] = useState("")
  const [documentTitle, setDocumentTitle] = useState("")
  const [documentBody, setDocumentBody] = useState("")
  const [importingDatasetId, setImportingDatasetId] = useState<string | null>(null)

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
  const datasetNameById = useMemo(() => {
    const map = new Map<string, string>()
    for (const dataset of datasets) map.set(dataset.id, dataset.name)
    return map
  }, [datasets])
  const selectedTypeMeta = datasetTypeMeta(datasetType)
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
      toast.error(formatTrainingError(error) || "Failed to create dataset")
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
      setBulkText("")
      await mutateDatasets()
    } catch (error) {
      console.error("[v0] Add record failed:", error)
      toast.error("Failed to add record", { description: formatTrainingError(error) })
    } finally {
      setMutatingDatasetId((current) => (current === datasetId ? null : current))
    }
  }

  function parseBulkExamples(text: string): { input: string; expected_output: string }[] {
    const lines = text
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
    const pairs: { input: string; expected_output: string }[] = []
    for (const line of lines) {
      if (line.includes("\t")) {
        const [input, ...rest] = line.split("\t")
        const expected = rest.join("\t").trim()
        if (input?.trim() && expected) pairs.push({ input: input.trim(), expected_output: expected })
        continue
      }
      const arrow = line.split(/\s+=>\s+|\s+→\s+/)
      if (arrow.length >= 2) {
        const input = arrow[0]?.trim()
        const expected = arrow.slice(1).join(" => ").trim()
        if (input && expected) pairs.push({ input, expected_output: expected })
      }
    }
    return pairs
  }

  async function handleBulkExamples(datasetId: string) {
    const pairs = parseBulkExamples(bulkText)
    if (pairs.length === 0) {
      toast.error("Paste lines as input => expected output (or tab-separated)")
      return
    }
    try {
      setMutatingDatasetId(datasetId)
      await ensureSelectedOrg(true)
      await trainingApi.uploadRecords(datasetId, pairs)
      toast.success(`Added ${pairs.length} example${pairs.length === 1 ? "" : "s"}`)
      setBulkText("")
      setRecordDatasetId(null)
      await mutateDatasets()
    } catch (error) {
      toast.error("Failed to add examples", { description: formatTrainingError(error) })
    } finally {
      setMutatingDatasetId((current) => (current === datasetId ? null : current))
    }
  }

  async function handleImportDocument(datasetId: string) {
    if (!documentBody.trim()) {
      toast.error("Document text is required")
      return
    }
    try {
      setImportingDatasetId(datasetId)
      await ensureSelectedOrg(true)
      const result = await trainingApi.importDocuments(datasetId, [
        { title: documentTitle.trim() || "Document", content: documentBody.trim() },
      ])
      toast.success(`Imported ${result.added} document${result.added === 1 ? "" : "s"}`)
      setDocumentTitle("")
      setDocumentBody("")
      setRecordDatasetId(null)
      await mutateDatasets()
    } catch (error) {
      toast.error("Failed to import document", { description: formatTrainingError(error) })
    } finally {
      setImportingDatasetId(null)
    }
  }

  async function handleImportDocumentFiles(datasetId: string, files: FileList | null) {
    if (!files?.length) return
    const documents: { title: string; content: string }[] = []
    for (const file of Array.from(files)) {
      if (!/\.(txt|md|markdown|jsonl)$/i.test(file.name) && !file.type.startsWith("text/")) {
        toast.error(`Unsupported file: ${file.name}. Use .txt or .md`)
        continue
      }
      const content = (await file.text()).trim()
      if (content) documents.push({ title: file.name, content })
    }
    if (documents.length === 0) return
    try {
      setImportingDatasetId(datasetId)
      await ensureSelectedOrg(true)
      const result = await trainingApi.importDocuments(datasetId, documents)
      toast.success(`Imported ${result.added} document${result.added === 1 ? "" : "s"}`)
      setRecordDatasetId(null)
      await mutateDatasets()
    } catch (error) {
      toast.error("Failed to import files", { description: formatTrainingError(error) })
    } finally {
      setImportingDatasetId(null)
    }
  }

  async function handleImportFeedback(datasetId: string) {
    try {
      setImportingDatasetId(datasetId)
      await ensureSelectedOrg(true)
      const result = await trainingApi.importFeedback(datasetId, 50)
      if (result.added === 0) {
        toast.message("No new feedback to import", {
          description: "Rate answers in chat as helpful or not helpful, then try again.",
        })
      } else {
        toast.success(`Imported ${result.added} feedback record${result.added === 1 ? "" : "s"}`)
      }
      await mutateDatasets()
    } catch (error) {
      toast.error("Failed to import feedback", { description: formatTrainingError(error) })
    } finally {
      setImportingDatasetId(null)
    }
  }

  async function handleCreateJob(datasetId: string) {
    if (!trainModelBase.trim()) return
    try {
      setMutatingDatasetId(datasetId)
      await ensureSelectedOrg(true)
      await trainingApi.createJob(datasetId, trainModelBase.trim())
      toast.success("Training job started")
      setTrainDatasetId(null)
      await mutateJobs()
    } catch (error) {
      console.error("[v0] Create job failed:", error)
      toast.error("Failed to start training job", { description: formatTrainingError(error) })
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
    <AppShell title={SURFACE_COPY.training.title}>
      <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
        <AgentsHubTabs active="training" />
        <LearningSurfacesCallout current="agent-training" />

        <PageHeader
          title={SURFACE_COPY.training.title}
          description={SURFACE_COPY.training.description}
          icon={Brain}
          iconColor="from-emerald-500/20 to-teal-500/20 ring-emerald-500/20"
          className="rounded-2xl border border-border/70 bg-card/40 p-4 sm:p-6"
          actions={
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                void mutateDatasets()
                void mutateJobs()
                void mutateInstructions()
              }}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
          }
        />

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
          <div className="rounded-xl border border-dashed border-emerald-500/25 bg-emerald-500/5 px-4 py-4 text-sm flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <span className="text-muted-foreground">
              No training datasets, jobs, or instructions yet. Create a dataset below or load starter examples.
            </span>
            <Button
              size="sm"
              variant="outline"
              className="border-emerald-500/30 hover:bg-emerald-500/10"
              disabled={isCreatingStarter}
              onClick={() => void handleCreateStarterDataset()}
            >
              {isCreatingStarter ? "Creating..." : "Load starter examples"}
            </Button>
          </div>
        ) : null}

        <TrainingOverview
          totalDatasets={stats.totalDatasets}
          readyDatasets={stats.readyDatasets}
          totalJobs={stats.totalJobs}
          activeJobs={stats.activeJobs}
          totalInstructions={stats.totalInstructions}
        />

        <div className="flex items-center justify-end">
          <DataFreshness
            updatedAt={datasetsData || jobsData ? Date.now() : null}
            onRefresh={() => {
              void mutateDatasets()
              void mutateJobs()
              void mutateInstructions()
            }}
          />
        </div>

        <StatsGrid columns={3} className="md:grid-cols-6">
          <StatCard label="Datasets" value={stats.totalDatasets} />
          <StatCard label="Ready" value={stats.readyDatasets} variant="success" />
          <StatCard label="Jobs" value={stats.totalJobs} />
          <StatCard label="Active jobs" value={stats.activeJobs} variant="info" />
          <StatCard label="Instructions" value={stats.totalInstructions} />
          <StatCard label="Active" value={stats.activeInstructions} variant="success" />
        </StatsGrid>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <motion.section
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 }}
            className="rounded-2xl border border-border/70 bg-card/80 p-5 shadow-sm backdrop-blur-sm space-y-4"
          >
            <div className="space-y-1">
              <h2 className="text-lg font-semibold text-foreground">Training Datasets</h2>
              <p className="text-sm text-muted-foreground">
                Pick a type, add teaching material, then run a job when you have enough records.
              </p>
            </div>

            <div className="space-y-3 rounded-xl border border-border/50 bg-background/40 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Dataset type</p>
              <div className="grid gap-2 sm:grid-cols-3">
                {DATASET_TYPE_META.map((meta) => {
                  const selected = datasetType === meta.value
                  return (
                    <button
                      key={meta.value}
                      type="button"
                      onClick={() => setDatasetType(meta.value)}
                      className={cn(
                        "rounded-xl border px-3 py-2.5 text-left transition-colors",
                        selected
                          ? "border-emerald-500/40 bg-emerald-500/10 ring-1 ring-emerald-500/30"
                          : "border-border/70 bg-background/60 hover:border-emerald-500/25 hover:bg-background/80"
                      )}
                    >
                      <p className="text-sm font-medium text-foreground">{meta.label}</p>
                      <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">{meta.summary}</p>
                    </button>
                  )
                })}
              </div>
              <p className="text-xs text-muted-foreground">
                {selectedTypeMeta.howToAdd} {selectedTypeMeta.trainHint}
              </p>
              <input
                value={datasetName}
                onChange={(event) => setDatasetName(event.target.value)}
                placeholder={`${selectedTypeMeta.label} dataset name`}
                className="w-full rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
              />
              <textarea
                value={datasetDescription}
                onChange={(event) => setDatasetDescription(event.target.value)}
                placeholder="What should this teach agents? (optional)"
                className="min-h-16 w-full rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
              />
              <div className="flex flex-wrap gap-2">
                <Button
                  className="bg-gradient-to-r from-emerald-500 to-teal-500 text-white hover:from-emerald-600 hover:to-teal-600"
                  onClick={() => void handleCreateDataset()}
                  disabled={isCreatingDataset || !datasetName.trim()}
                >
                  {isCreatingDataset ? "Creating..." : `Create ${selectedTypeMeta.label} dataset`}
                </Button>
                {datasetType === "examples" && (
                  <Button
                    variant="outline"
                    disabled={isCreatingStarter}
                    onClick={() => void handleCreateStarterDataset()}
                  >
                    {isCreatingStarter ? "Creating..." : "Load starter examples"}
                  </Button>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <AnimatePresence initial={false}>
                {datasets.map((dataset) => {
                  const typeMeta = datasetTypeMeta(dataset.type)
                  const isOpen = recordDatasetId === dataset.id
                  const isTraining = trainDatasetId === dataset.id
                  const busy = mutatingDatasetId === dataset.id || importingDatasetId === dataset.id
                  return (
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
                        <div className="min-w-0 space-y-1">
                          <p className="font-medium text-foreground">{dataset.name}</p>
                          <div className="flex flex-wrap items-center gap-1.5">
                            <span className="rounded-md border border-emerald-500/20 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-medium text-emerald-600 dark:text-emerald-300">
                              {typeMeta.label}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {dataset.record_count} record{dataset.record_count === 1 ? "" : "s"} ·{" "}
                              {formatDate(dataset.created_at)}
                            </span>
                          </div>
                          <p className="text-[11px] leading-relaxed text-muted-foreground">{typeMeta.summary}</p>
                        </div>
                        <span
                          className={cn(
                            "shrink-0 rounded-full border px-2 py-0.5 text-[10px] uppercase",
                            statusClasses(dataset.status)
                          )}
                        >
                          {dataset.status}
                        </span>
                      </div>
                      {dataset.description ? (
                        <p className="mt-2 text-xs text-muted-foreground">{dataset.description}</p>
                      ) : null}

                      {isOpen && dataset.type === "examples" && (
                        <div className="mt-3 space-y-3 rounded-lg border border-border/60 bg-background/50 p-3">
                          <div className="grid grid-cols-1 gap-2">
                            <textarea
                              value={recordInput}
                              onChange={(event) => setRecordInput(event.target.value)}
                              placeholder="User / situation input"
                              className="min-h-16 rounded-lg border border-border bg-background/80 px-3 py-2 text-sm"
                            />
                            <textarea
                              value={recordOutput}
                              onChange={(event) => setRecordOutput(event.target.value)}
                              placeholder="Ideal agent answer"
                              className="min-h-16 rounded-lg border border-border bg-background/80 px-3 py-2 text-sm"
                            />
                            <div className="flex flex-wrap gap-2">
                              <Button
                                size="sm"
                                onClick={() => void handleAddRecord(dataset.id)}
                                disabled={busy}
                              >
                                Save example
                              </Button>
                              <Button size="sm" variant="ghost" onClick={() => setRecordDatasetId(null)}>
                                Cancel
                              </Button>
                            </div>
                          </div>
                          <div className="space-y-2 border-t border-border/50 pt-3">
                            <p className="text-xs font-medium text-foreground">Bulk paste</p>
                            <p className="text-[11px] text-muted-foreground">
                              One pair per line: input =&gt; expected output (or tab-separated).
                            </p>
                            <textarea
                              value={bulkText}
                              onChange={(event) => setBulkText(event.target.value)}
                              placeholder={"What is our refund policy? => Refunds within 30 days...\nEscalate VIP tickets => Notify account owner within 15 minutes"}
                              className="min-h-20 w-full rounded-lg border border-border bg-background/80 px-3 py-2 text-sm"
                            />
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => void handleBulkExamples(dataset.id)}
                              disabled={busy || !bulkText.trim()}
                            >
                              Import pasted examples
                            </Button>
                          </div>
                        </div>
                      )}

                      {isOpen && dataset.type === "documents" && (
                        <div className="mt-3 space-y-3 rounded-lg border border-border/60 bg-background/50 p-3">
                          <p className="text-[11px] text-muted-foreground">{typeMeta.howToAdd}</p>
                          <input
                            value={documentTitle}
                            onChange={(event) => setDocumentTitle(event.target.value)}
                            placeholder="Document title (optional)"
                            className="w-full rounded-lg border border-border bg-background/80 px-3 py-2 text-sm"
                          />
                          <textarea
                            value={documentBody}
                            onChange={(event) => setDocumentBody(event.target.value)}
                            placeholder="Paste policy, playbook, or reference text..."
                            className="min-h-28 w-full rounded-lg border border-border bg-background/80 px-3 py-2 text-sm"
                          />
                          <div className="flex flex-wrap items-center gap-2">
                            <Button
                              size="sm"
                              onClick={() => void handleImportDocument(dataset.id)}
                              disabled={busy || !documentBody.trim()}
                            >
                              {importingDatasetId === dataset.id ? "Importing..." : "Import pasted text"}
                            </Button>
                            <label
                              className={cn(
                                "inline-flex h-8 cursor-pointer items-center justify-center rounded-md border border-input bg-background px-3 text-xs font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground",
                                busy && "pointer-events-none opacity-50"
                              )}
                            >
                              <input
                                type="file"
                                accept=".txt,.md,.markdown,text/plain"
                                multiple
                                className="sr-only"
                                disabled={busy}
                                onChange={(event) => {
                                  void handleImportDocumentFiles(dataset.id, event.target.files)
                                  event.target.value = ""
                                }}
                              />
                              {busy ? "Uploading..." : "Upload .txt / .md"}
                            </label>
                            <Button size="sm" variant="ghost" onClick={() => setRecordDatasetId(null)}>
                              Cancel
                            </Button>
                          </div>
                        </div>
                      )}

                      {isOpen && dataset.type === "feedback" && (
                        <div className="mt-3 space-y-3 rounded-lg border border-border/60 bg-background/50 p-3">
                          <p className="text-[11px] text-muted-foreground">
                            Pull helpful / not-helpful ratings from chat, or add a corrected example by hand.
                          </p>
                          <Button
                            size="sm"
                            onClick={() => void handleImportFeedback(dataset.id)}
                            disabled={busy}
                          >
                            {importingDatasetId === dataset.id
                              ? "Importing..."
                              : "Import recent chat feedback"}
                          </Button>
                          <div className="grid grid-cols-1 gap-2 border-t border-border/50 pt-3">
                            <textarea
                              value={recordInput}
                              onChange={(event) => setRecordInput(event.target.value)}
                              placeholder="Original user message"
                              className="min-h-16 rounded-lg border border-border bg-background/80 px-3 py-2 text-sm"
                            />
                            <textarea
                              value={recordOutput}
                              onChange={(event) => setRecordOutput(event.target.value)}
                              placeholder="Corrected / preferred answer"
                              className="min-h-16 rounded-lg border border-border bg-background/80 px-3 py-2 text-sm"
                            />
                            <div className="flex flex-wrap gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => void handleAddRecord(dataset.id)}
                                disabled={busy}
                              >
                                Save corrected example
                              </Button>
                              <Button size="sm" variant="ghost" onClick={() => setRecordDatasetId(null)}>
                                Cancel
                              </Button>
                            </div>
                          </div>
                        </div>
                      )}

                      {isTraining && (
                        <div className="mt-3 space-y-2 rounded-lg border border-border/60 bg-background/50 p-3">
                          <p className="text-xs text-muted-foreground">
                            Fine-tune a supported base model on this dataset ({dataset.record_count} records).
                            Progress appears under Training Jobs.
                          </p>
                          <div className="flex flex-wrap items-center gap-2">
                            <select
                              value={trainModelBase}
                              onChange={(event) => setTrainModelBase(event.target.value)}
                              aria-label="Base model"
                              className="rounded-lg border border-border bg-background/80 px-3 py-2 text-sm"
                            >
                              {TRAINABLE_BASE_MODELS.map((model) => (
                                <option key={model.id} value={model.id}>
                                  {model.label}
                                </option>
                              ))}
                            </select>
                            <Button
                              size="sm"
                              onClick={() => void handleCreateJob(dataset.id)}
                              disabled={busy || dataset.record_count < 1}
                            >
                              Start training job
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => setTrainDatasetId(null)}>
                              Cancel
                            </Button>
                          </div>
                        </div>
                      )}

                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          className="hover:border-emerald-500/40 hover:text-emerald-400"
                          disabled={busy}
                          onClick={() => {
                            setTrainDatasetId(null)
                            const next = isOpen ? null : dataset.id
                            setRecordDatasetId(next)
                            setRecordInput("")
                            setRecordOutput("")
                            setBulkText("")
                            setDocumentTitle("")
                            setDocumentBody("")
                          }}
                        >
                          {dataset.type === "documents"
                            ? "Add documents"
                            : dataset.type === "feedback"
                              ? "Add feedback"
                              : "Add examples"}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="hover:border-blue-500/40 hover:text-blue-400"
                          disabled={busy || dataset.record_count < 1}
                          onClick={() => {
                            setRecordDatasetId(null)
                            setTrainDatasetId(isTraining ? null : dataset.id)
                          }}
                        >
                          Train
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="hover:border-red-500/40 hover:text-red-400"
                          disabled={busy}
                          onClick={() => void handleDeleteDataset(dataset.id)}
                        >
                          Delete
                        </Button>
                      </div>
                    </motion.div>
                  )
                })}
              </AnimatePresence>
              {datasets.length === 0 && (
                <div className="rounded-xl border border-dashed border-border/70 px-4 py-6 text-center">
                  <p className="text-sm text-muted-foreground">
                    No datasets yet. Create one above, or load starter examples to see the full flow.
                  </p>
                </div>
              )}
            </div>
          </motion.section>

          <motion.section
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.14 }}
            className="rounded-2xl border border-border/70 bg-card/80 p-5 shadow-sm backdrop-blur-sm space-y-4"
          >
            <div className="space-y-1">
              <h2 className="text-lg font-semibold text-foreground">Training Jobs</h2>
              <p className="text-sm text-muted-foreground">
                Fine-tune runs started from a dataset. When a job completes, assign the model below.
              </p>
            </div>
            <div className="space-y-2">
              <AnimatePresence initial={false}>
                {jobs.map((job) => {
                  const datasetLabel =
                    datasetNameById.get(job.dataset_id) ?? `Dataset ${job.dataset_id.slice(0, 8)}`
                  const statusHint =
                    job.status === "queued"
                      ? "Waiting to start"
                      : job.status === "training"
                        ? "Fine-tuning in progress"
                        : job.status === "completed"
                          ? "Ready to assign to an agent"
                          : job.status === "failed"
                            ? "Job failed. Check records and try again"
                            : job.status === "cancelled"
                              ? "Cancelled"
                              : job.status
                  return (
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
                        <div className="min-w-0">
                          <p className="font-medium text-foreground">{datasetLabel}</p>
                          <p className="text-xs text-muted-foreground">
                            Base {job.model_base} · {formatDate(job.created_at)}
                          </p>
                          <p className="mt-1 text-[11px] text-muted-foreground">
                            {statusHint} · {job.progress}%
                          </p>
                        </div>
                        <span
                          className={cn(
                            "shrink-0 rounded-full border px-2 py-0.5 text-[10px] uppercase",
                            statusClasses(job.status)
                          )}
                        >
                          {job.status}
                        </span>
                      </div>
                      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-secondary">
                        <motion.div
                          className="relative h-full overflow-hidden bg-gradient-to-r from-blue-500 to-cyan-400"
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
                      {(job.status === "queued" || job.status === "training") && (
                        <div className="mt-3 flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            className="hover:border-red-500/40 hover:text-red-400"
                            disabled={mutatingJobId === job.id}
                            onClick={() => void handleCancelJob(job.id)}
                          >
                            Cancel
                          </Button>
                        </div>
                      )}
                    </motion.div>
                  )
                })}
              </AnimatePresence>
              {jobs.length === 0 && (
                <div className="rounded-xl border border-dashed border-border/70 px-4 py-6 text-center">
                  <p className="text-sm text-muted-foreground">
                    No jobs yet. Add records to a dataset, then click Train.
                  </p>
                </div>
              )}
            </div>
          </motion.section>
        </div>

        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="rounded-2xl border border-border/70 bg-card/80 p-5 shadow-sm backdrop-blur-sm space-y-4"
        >
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-foreground">Custom Instructions</h2>
            <p className="text-sm text-muted-foreground">
              Live prompt guidance injected into agent chats when enabled. Use this for tone, escalation rules, and
              standing policies without waiting for a fine-tune.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-2 rounded-xl border border-border/50 bg-background/40 p-3">
            <input
              value={instructionName}
              onChange={(event) => setInstructionName(event.target.value)}
              placeholder="Instruction name (e.g. Escalation tone)"
              className="rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
            />
            <select
              value={effectiveSelectedAgentId}
              onChange={(event) => setSelectedAgentId(event.target.value)}
              aria-label="Apply instruction to agent"
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
              placeholder="When enabled, this text is added to the agent system prompt (e.g. Always confirm before sending customer email)."
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
          className="rounded-2xl border border-border/70 bg-card/80 p-5 shadow-sm backdrop-blur-sm space-y-4"
        >
          <h2 className="text-lg font-semibold text-foreground">Assign Fine-Tuned Models</h2>
          <p className="text-sm text-muted-foreground">
            After a job completes, attach the model to a workflow agent. Chat falls back to the agent base model if
            the fine-tuned provider call fails.
          </p>
          <div className="grid grid-cols-1 gap-2 rounded-xl border border-border/50 bg-background/40 p-3 md:grid-cols-2">
            <select
              value={effectiveAssignAgentId}
              onChange={(event) => {
                setAssignAgentId(event.target.value)
                setAssignModelId("")
              }}
              aria-label="Workflow agent"
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
              aria-label="Fine-tuned model assignment"
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
        <AppShell title={SURFACE_COPY.training.title}>
          <div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">
            Loading training…
          </div>
        </AppShell>
      }
    >
      <TrainingPageContent />
    </Suspense>
  )
}
