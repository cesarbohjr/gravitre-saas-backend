"use client"

import { useMemo, useState, useEffect, useRef } from "react"
import useSWR from "swr"
import { useSearchParams } from "next/navigation"
import Link from "next/link"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import { toast } from "sonner"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { AppShell } from "@/components/gravitre/app-shell"
import { DataFreshness } from "@/components/gravitre/data-freshness"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import { trainingApi, agentsApi } from "@/lib/api"
import { ensureSelectedOrg } from "@/lib/org-context"
import type {
  CustomInstruction,
  TrainingDatasetType,
  WorkflowAgent,
} from "@/types/api"
import { cn } from "@/lib/utils"
import { LearningSurfacesCallout } from "@/components/gravitre/learning-surfaces-callout"
import { AgentsHubTabs } from "@/components/agents/agents-hub-tabs"
import {
  GravitreMetric,
  GravitrePageHeader,
} from "@/components/gravitre/nodus-product"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { TrainingOverview } from "@/components/gravitre/training-overview"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  parseTrainingExamples,
  reportedTrainingProgress,
} from "@/lib/training-journey"
import { TYPE } from "@/lib/design-system"
import { Tabs, TabsContent } from "@/components/ui/tabs"
import { APP_ROUTES } from "@/lib/app-routes"
import { SURFACE_COPY } from "@/lib/surface-copy"
import {
  DATASET_TYPE_META,
  TRAINABLE_BASE_MODELS,
  datasetTypeMeta,
} from "@/lib/training-ui-copy"
import { RefreshCw } from "lucide-react"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { STARTER_DATASET, STARTER_EXAMPLES } from "@/components/training/starter-examples"

function statusClasses(status: string): string {
  if (status === "ready" || status === "completed") {
    return "bg-success/10 text-success border-success/20"
  }
  if (status === "training" || status === "processing" || status === "queued") {
    return "bg-info/10 text-info border-info/20"
  }
  if (status === "failed") {
    return "bg-destructive/10 text-destructive border-destructive/20"
  }
  return "bg-secondary text-muted-foreground border-border"
}

function formatDate(value?: string): string {
  if (!value) return "Not reported"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return "Not reported"
  return parsed.toLocaleString()
}

function formatTrainingError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error ?? "")
  if (/org|membership|403|forbidden/i.test(message))
    return "Your workspace could not authorize this action. Check your membership and try again."
  return "Training is unavailable right now. Your edits are retained; try again."
}


export type TrainingSection = "datasets" | "jobs" | "instructions" | "models"

/**
 * The training workbench. On its own route it is Agents › Instructions; on
 * Intelligence › Data and Models it is mounted `embedded` with one fixed
 * `section`, so each feature has one home and no inner tabs.
 */
export function TrainingWorkbench({
  embedded = false,
  section,
  focusDataset,
}: {
  embedded?: boolean
  section?: TrainingSection
  /** Open this dataset's editor (Intelligence › Data rows and "Train with this dataset"). */
  focusDataset?: { id: string; nonce: number } | null
} = {}) {
  const reduced = useReducedMotion()
  const mutationRef = useRef(false)
  const [mutationPending, setMutationPending] = useState(false)
  const [mutationError, setMutationError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<{
    kind: "dataset" | "instruction" | "job"
    id: string
    name: string
  } | null>(null)
  const [starterDatasetId, setStarterDatasetId] = useState<string | null>(null)
  function beginMutation() {
    if (mutationRef.current || !orgReady) return false
    mutationRef.current = true
    setMutationPending(true)
    setMutationError(null)
    return true
  }
  function endMutation() {
    mutationRef.current = false
    setMutationPending(false)
  }
  const searchParams = useSearchParams()
  const agentFilterId = searchParams.get("agentId") ?? ""
  const { user } = useAuth()
  const [orgReady, setOrgReady] = useState(false)
  const [orgError, setOrgError] = useState<string | null>(null)
  const [datasetName, setDatasetName] = useState("")
  const [datasetDescription, setDatasetDescription] = useState("")
  const [datasetType, setDatasetType] =
    useState<TrainingDatasetType>("examples")
  const [instructionName, setInstructionName] = useState("")
  const [instructionContent, setInstructionContent] = useState("")
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)
  const [isCreatingDataset, setIsCreatingDataset] = useState(false)
  const [isCreatingInstruction, setIsCreatingInstruction] = useState(false)
  const [mutatingDatasetId, setMutatingDatasetId] = useState<string | null>(
    null,
  )
  const [mutatingJobId, setMutatingJobId] = useState<string | null>(null)
  const [mutatingInstructionId, setMutatingInstructionId] = useState<
    string | null
  >(null)
  const [assignAgentId, setAssignAgentId] = useState<string>("")
  const [assignModelId, setAssignModelId] = useState<string | null>(null)
  const [isAssigningModel, setIsAssigningModel] = useState(false)
  const [recordDatasetId, setRecordDatasetId] = useState<string | null>(null)
  const [recordInput, setRecordInput] = useState("")
  const [recordOutput, setRecordOutput] = useState("")
  const [trainDatasetId, setTrainDatasetId] = useState<string | null>(null)
  const [trainModelBase, setTrainModelBase] = useState<string>(
    TRAINABLE_BASE_MODELS[0].id,
  )
  const [isCreatingStarter, setIsCreatingStarter] = useState(false)
  const [bulkText, setBulkText] = useState("")
  const [documentTitle, setDocumentTitle] = useState("")
  const [documentBody, setDocumentBody] = useState("")
  const [importingDatasetId, setImportingDatasetId] = useState<string | null>(
    null,
  )
  const [trainingTab, setTrainingTab] = useState<string>(section ?? "datasets")
  const materialDrafts = useRef<
    Record<
      string,
      {
        input: string
        output: string
        bulk: string
        title: string
        body: string
      }
    >
  >({})
  function chooseMaterial(next: string | null) {
    if (mutationRef.current) return
    if (recordDatasetId)
      materialDrafts.current[recordDatasetId] = {
        input: recordInput,
        output: recordOutput,
        bulk: bulkText,
        title: documentTitle,
        body: documentBody,
      }
    setRecordDatasetId(next)
    setTrainDatasetId(null)
    const draft = next ? materialDrafts.current[next] : undefined
    setRecordInput(draft?.input ?? "")
    setRecordOutput(draft?.output ?? "")
    setBulkText(draft?.bulk ?? "")
    setDocumentTitle(draft?.title ?? "")
    setDocumentBody(draft?.body ?? "")
  }

  const focusNonce = focusDataset?.nonce
  useEffect(() => {
    if (!focusDataset?.id) return
    setTrainingTab("datasets")
    chooseMaterial(focusDataset.id)
    // Only a new request (nonce) should move the editor.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusNonce])

  useEffect(() => {
    let cancelled = false
    setOrgReady(false)
    setOrgError(null)
    if (user)
      void ensureSelectedOrg(true)
        .then((orgId) => {
          if (!cancelled) {
            setOrgReady(Boolean(orgId))
            setOrgError(
              orgId
                ? null
                : "Workspace membership is required to load training.",
            )
          }
        })
        .catch(() => {
          if (!cancelled)
            setOrgError("Could not load your workspace. Try again.")
        })
    return () => {
      cancelled = true
    }
  }, [user])

  const swrKey = user && orgReady ? "training" : null

  const [trainingUpdatedAt, setTrainingUpdatedAt] = useState<number | null>(
    null,
  )
  const {
    data: datasetsData,
    error: datasetsError,
    mutate: mutateDatasets,
    isLoading: datasetsLoading,
  } = useSWR(
    swrKey ? "training/datasets" : null,
    () => trainingApi.listDatasets(),
    {
      revalidateOnFocus: false,
      onSuccess: () => setTrainingUpdatedAt(Date.now()),
    },
  )
  const {
    data: jobsData,
    error: jobsError,
    mutate: mutateJobs,
    isLoading: jobsLoading,
  } = useSWR(swrKey ? "training/jobs" : null, () => trainingApi.listJobs(), {
    onSuccess: () => setTrainingUpdatedAt(Date.now()),
    revalidateOnFocus: false,
    refreshInterval: (latest) => {
      const active = (latest?.jobs ?? []).some(
        (job) => job.status === "queued" || job.status === "training",
      )
      return active ? 5000 : 0
    },
  })
  const {
    data: instructionsData,
    error: instructionsError,
    mutate: mutateInstructions,
    isLoading: instructionsLoading,
  } = useSWR(
    swrKey ? "training/instructions" : null,
    () => trainingApi.listInstructions(),
    {
      revalidateOnFocus: false,
      onSuccess: () => setTrainingUpdatedAt(Date.now()),
    },
  )
  const {
    data: workflowAgentsData,
    error: workflowAgentsError,
    isLoading: workflowAgentsLoading,
    mutate: mutateWorkflowAgents,
  } = useSWR(
    swrKey ? "training/workflow-agents" : null,
    () => trainingApi.listWorkflowAgents(),
    { revalidateOnFocus: false },
  )
  const {
    data: agentsFallbackData,
    error: agentsFallbackError,
    isLoading: agentsFallbackLoading,
    mutate: mutateAgentsFallback,
  } = useSWR(
    swrKey && workflowAgentsData && (workflowAgentsData.agents ?? []).length === 0
      ? "training/agents-fallback"
      : null,
    async () => {
      const response = await agentsApi.list()
      const raw = response.agents ?? []
      return raw.map(
        (agent): WorkflowAgent => ({
          id: String(agent.id),
          name: String(agent.name ?? "Agent"),
          role: agent.role,
          status: agent.status,
        }),
      )
    },
    { revalidateOnFocus: false },
  )
  const {
    data: fineTunedModelsData,
    error: modelsError,
    isLoading: modelsLoading,
    mutate: mutateModels,
  } = useSWR(
    swrKey ? "training/fine-tuned-models" : null,
    () => trainingApi.listFineTunedModels(),
    { revalidateOnFocus: false },
  )

  const datasets = useMemo(() => datasetsData?.datasets ?? [], [datasetsData])
  const jobs = useMemo(() => jobsData?.jobs ?? [], [jobsData])
  const instructions = useMemo(
    () => instructionsData?.instructions ?? [],
    [instructionsData],
  )
  const scopedDatasetId = recordDatasetId ?? trainDatasetId
  const scopedDataset = datasets.find(dataset => dataset.id === scopedDatasetId)
  usePublishGravitreAISelection(scopedDataset ? { kind: "training-dataset", id: scopedDataset.id, label: scopedDataset.name } : null)
  const trainingLoading = datasetsLoading || jobsLoading || instructionsLoading

  const workflowAgents = useMemo(
    () => workflowAgentsData?.agents ?? [],
    [workflowAgentsData],
  )
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
  const filteredAgent = assignableAgents.find(
    (agent) => agent.id === agentFilterId,
  )
  const visibleInstructions = useMemo(() => {
    if (!agentFilterId) return instructions
    return instructions.filter(
      (instruction) =>
        !instruction.agent_id || instruction.agent_id === agentFilterId,
    )
  }, [instructions, agentFilterId])

  const effectiveSelectedAgentId = selectedAgentId ?? agentFilterId ?? ""
  const effectiveAssignAgentId = assignAgentId || agentFilterId || ""
  const assignedModelForAgent = assignableAgents.find(
    (a) => a.id === effectiveAssignAgentId,
  )?.trainedModelId
  const effectiveAssignModelId = assignModelId ?? assignedModelForAgent ?? ""

  const stats = useMemo(() => {
    const readyDatasets = datasets.filter((d) => d.status === "ready").length
    const queuedJobs = jobs.filter((j) => j.status === "queued").length
    const runningJobs = jobs.filter((j) => j.status === "training").length
    const failedJobs = jobs.filter((j) => j.status === "failed").length
    const readyJobs = jobs.filter((j) => j.status === "completed").length
    const activeJobs = queuedJobs + runningJobs
    const activeInstructions = instructions.filter((i) => i.is_active).length
    const scopedInstructions = agentFilterId
      ? instructions.filter((i) => !i.agent_id || i.agent_id === agentFilterId)
          .length
      : instructions.length
    return {
      totalDatasets: datasets.length,
      readyDatasets,
      totalJobs: jobs.length,
      activeJobs,
      queuedJobs,
      runningJobs,
      failedJobs,
      readyJobs,
      totalInstructions: scopedInstructions,
      activeInstructions,
    }
  }, [datasets, jobs, instructions, agentFilterId])

  async function handleCreateDataset() {
    if (!datasetName.trim()) return
    if (!beginMutation()) return
    try {
      setIsCreatingDataset(true)
      if (!(await ensureSelectedOrg(true)))
        throw new Error("Workspace membership required")
      await trainingApi.createDataset({
        name: datasetName.trim(),
        type: datasetType,
        description: datasetDescription.trim() || undefined,
      })
      toast.success("Dataset created")
      setDatasetName("")
      setDatasetDescription("")
      setDatasetType("examples")
      await Promise.allSettled([mutateDatasets()])
    } catch (error) {
      setMutationError(formatTrainingError(error))
      console.error("[v0] Create dataset failed:", error)
      toast.error(formatTrainingError(error) || "Failed to create dataset")
    } finally {
      endMutation()
      setIsCreatingDataset(false)
    }
  }

  async function handleDeleteDataset(datasetId: string) {
    if (!beginMutation()) return
    try {
      setMutatingDatasetId(datasetId)
      await trainingApi.deleteDataset(datasetId)
      setDeleteTarget(null)
      toast.success("Dataset deleted")
      await Promise.allSettled([mutateDatasets(), mutateJobs()])
    } catch (error) {
      setMutationError(formatTrainingError(error))
      console.error("[v0] Delete dataset failed:", error)
      toast.error("Failed to delete dataset")
    } finally {
      endMutation()
      setMutatingDatasetId((current) =>
        current === datasetId ? null : current,
      )
    }
  }

  async function handleCreateStarterDataset() {
    if (!beginMutation()) return
    try {
      setIsCreatingStarter(true)
      if (!(await ensureSelectedOrg(true)))
        throw new Error("Workspace membership required")
      const created = starterDatasetId
        ? { id: starterDatasetId }
        : await trainingApi.createDataset({ ...STARTER_DATASET })
      setStarterDatasetId(created.id)
      const result = await trainingApi.uploadRecords(created.id, [
        ...STARTER_EXAMPLES,
      ])
      setStarterDatasetId(null)
      toast.success(`Starter dataset imported ${result.added} example records`)
      setRecordDatasetId(null)
      await Promise.allSettled([mutateDatasets()])
    } catch (error) {
      setMutationError(formatTrainingError(error))
      void mutateDatasets()
      console.error("[training] Starter dataset failed:", error)
      toast.error("Failed to create starter dataset", {
        description: formatTrainingError(error),
      })
    } finally {
      endMutation()
      setIsCreatingStarter(false)
    }
  }

  async function handleAddRecord(datasetId: string) {
    if (!recordInput.trim() || !recordOutput.trim()) {
      toast.error("Input and expected output are required")
      return
    }
    if (!beginMutation()) return
    try {
      setMutatingDatasetId(datasetId)
      if (!(await ensureSelectedOrg(true)))
        throw new Error("Workspace membership required")
      const result = await trainingApi.uploadRecords(datasetId, [
        { input: recordInput.trim(), expected_output: recordOutput.trim() },
      ])
      toast.success(`Added ${result.added} training records`)
      setRecordInput("")
      setRecordOutput("")
      delete materialDrafts.current[datasetId]
      setRecordDatasetId(null)
      setBulkText("")
      await Promise.allSettled([mutateDatasets()])
    } catch (error) {
      setMutationError(formatTrainingError(error))
      console.error("[v0] Add record failed:", error)
      toast.error("Failed to add record", {
        description: formatTrainingError(error),
      })
    } finally {
      endMutation()
      setMutatingDatasetId((current) =>
        current === datasetId ? null : current,
      )
    }
  }

  async function handleBulkExamples(datasetId: string) {
    const { records: pairs, invalidLines } = parseTrainingExamples(bulkText)
    if (invalidLines.length) {
      setMutationError(
        `Fix lines ${invalidLines.join(", ")} before importing. Every nonempty line needs an input and expected output.`,
      )
      return
    }
    if (pairs.length === 0) {
      toast.error("Paste lines as input => expected output (or tab-separated)")
      return
    }
    if (!beginMutation()) return
    try {
      setMutatingDatasetId(datasetId)
      if (!(await ensureSelectedOrg(true)))
        throw new Error("Workspace membership required")
      const result = await trainingApi.uploadRecords(datasetId, pairs)
      toast.success(
        `Added ${result.added} example${result.added === 1 ? "" : "s"}`,
      )
      setBulkText("")
      delete materialDrafts.current[datasetId]
      setRecordDatasetId(null)
      await Promise.allSettled([mutateDatasets()])
    } catch (error) {
      setMutationError(formatTrainingError(error))
      toast.error("Failed to add examples", {
        description: formatTrainingError(error),
      })
    } finally {
      endMutation()
      setMutatingDatasetId((current) =>
        current === datasetId ? null : current,
      )
    }
  }

  async function handleImportDocument(datasetId: string) {
    if (!documentBody.trim()) {
      toast.error("Document text is required")
      return
    }
    if (!beginMutation()) return
    try {
      setImportingDatasetId(datasetId)
      if (!(await ensureSelectedOrg(true)))
        throw new Error("Workspace membership required")
      const result = await trainingApi.importDocuments(datasetId, [
        {
          title: documentTitle.trim() || "Document",
          content: documentBody.trim(),
        },
      ])
      toast.success(
        `Imported ${result.added} document${result.added === 1 ? "" : "s"}`,
      )
      setDocumentTitle("")
      setDocumentBody("")
      delete materialDrafts.current[datasetId]
      setRecordDatasetId(null)
      await Promise.allSettled([mutateDatasets()])
    } catch (error) {
      setMutationError(formatTrainingError(error))
      toast.error("Failed to import document", {
        description: formatTrainingError(error),
      })
    } finally {
      endMutation()
      setImportingDatasetId(null)
    }
  }

  async function handleImportDocumentFiles(
    datasetId: string,
    files: FileList | null,
  ) {
    if (!files?.length || !beginMutation()) return
    let readingFiles = true
    try {
      setImportingDatasetId(datasetId)
      const documents: { title: string; content: string }[] = []
      for (const file of Array.from(files)) {
        if (!/\.(txt|md|markdown)$/i.test(file.name))
          throw new Error(
            "Use .txt, .md or .markdown files. No files were imported.",
          )
        const content = (await file.text()).trim()
        if (!content)
          throw new Error(`${file.name} is empty. No files were imported.`)
        documents.push({ title: file.name, content })
      }
      readingFiles = false
      if (!(await ensureSelectedOrg(true)))
        throw new Error("Workspace membership required")
      const result = await trainingApi.importDocuments(datasetId, documents)
      toast.success(`Imported ${result.added} documents`)
      delete materialDrafts.current[datasetId]
      setRecordDatasetId(null)
      await Promise.allSettled([mutateDatasets()])
    } catch (error) {
      setMutationError(
        readingFiles && error instanceof Error
          ? error.message
          : formatTrainingError(error),
      )
      toast.error("Failed to import files")
    } finally {
      endMutation()
      setImportingDatasetId(null)
    }
  }

  async function handleImportFeedback(datasetId: string) {
    if (!beginMutation()) return
    try {
      setImportingDatasetId(datasetId)
      if (!(await ensureSelectedOrg(true)))
        throw new Error("Workspace membership required")
      const result = await trainingApi.importFeedback(datasetId, 50)
      if (result.added === 0) {
        toast.message("No new feedback to import", {
          description:
            "Rate answers in chat as helpful or not helpful, then try again.",
        })
      } else {
        toast.success(
          `Imported ${result.added} feedback record${result.added === 1 ? "" : "s"}`,
        )
      }
      await Promise.allSettled([mutateDatasets()])
    } catch (error) {
      setMutationError(formatTrainingError(error))
      toast.error("Failed to import feedback", {
        description: formatTrainingError(error),
      })
    } finally {
      endMutation()
      setImportingDatasetId(null)
    }
  }

  async function handleCreateJob(datasetId: string) {
    if (!trainModelBase.trim()) return
    if (!beginMutation()) return
    try {
      setMutatingDatasetId(datasetId)
      if (!(await ensureSelectedOrg(true)))
        throw new Error("Workspace membership required")
      await trainingApi.createJob(datasetId, trainModelBase.trim())
      toast.success("Training job requested")
      setTrainDatasetId(null)
      await Promise.allSettled([mutateJobs()])
    } catch (error) {
      setMutationError(formatTrainingError(error))
      console.error("[v0] Create job failed:", error)
      toast.error("Failed to start training job", {
        description: formatTrainingError(error),
      })
    } finally {
      endMutation()
      setMutatingDatasetId((current) =>
        current === datasetId ? null : current,
      )
    }
  }

  async function handleCancelJob(jobId: string) {
    if (!beginMutation()) return
    try {
      setMutatingJobId(jobId)
      await trainingApi.cancelJob(jobId)
      setDeleteTarget(null)
      toast.success("Training job cancelled")
      await Promise.allSettled([mutateJobs()])
    } catch (error) {
      setMutationError(formatTrainingError(error))
      console.error("[v0] Cancel job failed:", error)
      toast.error("Failed to cancel job")
    } finally {
      endMutation()
      setMutatingJobId((current) => (current === jobId ? null : current))
    }
  }

  async function handleCreateInstruction() {
    if (!instructionName.trim() || !instructionContent.trim()) return
    if (!beginMutation()) return
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
      await Promise.allSettled([mutateInstructions()])
    } catch (error) {
      setMutationError(formatTrainingError(error))
      console.error("[v0] Create instruction failed:", error)
      toast.error("Failed to create instruction")
    } finally {
      endMutation()
      setIsCreatingInstruction(false)
    }
  }

  async function handleToggleInstruction(instruction: CustomInstruction) {
    if (!beginMutation()) return
    try {
      setMutatingInstructionId(instruction.id)
      await trainingApi.toggleInstruction(
        instruction.id,
        !instruction.is_active,
      )
      toast.success(
        instruction.is_active ? "Instruction disabled" : "Instruction enabled",
      )
      await Promise.allSettled([mutateInstructions()])
    } catch (error) {
      setMutationError(formatTrainingError(error))
      console.error("[v0] Toggle instruction failed:", error)
      toast.error("Failed to update instruction")
    } finally {
      endMutation()
      setMutatingInstructionId((current) =>
        current === instruction.id ? null : current,
      )
    }
  }

  async function handleAssignFineTunedModel() {
    if (!effectiveAssignAgentId || assignModelId === null) return
    if (!beginMutation()) return
    try {
      setIsAssigningModel(true)
      await trainingApi.assignAgentFineTunedModel(
        effectiveAssignAgentId,
        effectiveAssignModelId ? effectiveAssignModelId : null,
      )
      toast.success(
        effectiveAssignModelId
          ? "Fine-tuned model assigned"
          : "Fine-tuned model cleared",
      )
      await Promise.allSettled([mutateWorkflowAgents()])
    } catch (error) {
      setMutationError(formatTrainingError(error))
      console.error("[v0] Assign fine-tuned model failed:", error)
      toast.error("Failed to assign fine-tuned model")
    } finally {
      endMutation()
      setIsAssigningModel(false)
    }
  }

  async function handleDeleteInstruction(instructionId: string) {
    if (!beginMutation()) return
    try {
      setMutatingInstructionId(instructionId)
      await trainingApi.deleteInstruction(instructionId)
      setDeleteTarget(null)
      toast.success("Instruction deleted")
      await Promise.allSettled([mutateInstructions()])
    } catch (error) {
      setMutationError(formatTrainingError(error))
      console.error("[v0] Delete instruction failed:", error)
      toast.error("Failed to delete instruction")
    } finally {
      endMutation()
      setMutatingInstructionId((current) =>
        current === instructionId ? null : current,
      )
    }
  }

  const loadError =
    orgError ??
    (datasetsError ? formatTrainingError(datasetsError) : null) ??
    (jobsError ? formatTrainingError(jobsError) : null) ??
    (instructionsError ? formatTrainingError(instructionsError) : null)

  const pageTitle = section === "instructions" ? SURFACE_COPY.trainingInstructions.title : SURFACE_COPY.training.title
  const pageDescription =
    section === "instructions" ? SURFACE_COPY.trainingInstructions.description : SURFACE_COPY.training.description

  const body = (
      <div
        className={embedded ? "space-y-6" : "mx-auto max-w-6xl space-y-6 p-4 pb-20 sm:p-6"}
        data-composition="create"
      >
        {!embedded ? <AgentsHubTabs active="training" /> : null}
        {!embedded && !section ? <LearningSurfacesCallout current="agent-training" /> : null}
        {section === "instructions" && !embedded ? (
          <p className={TYPE.bodyMuted}>
            Looking for datasets or fine-tunes? They now live in{" "}
            <Link href={APP_ROUTES.intelligenceData} className="font-medium text-[color:var(--g-brand-active)] hover:underline">
              Intelligence › Data
            </Link>{" "}
            and{" "}
            <Link href={APP_ROUTES.models} className="font-medium text-[color:var(--g-brand-active)] hover:underline">
              Models
            </Link>
            .
          </p>
        ) : null}

        {!embedded ? (
        <GravitrePageHeader
          className="px-0 sm:px-0"
          title={pageTitle}
          description={pageDescription}
          icon={<NucleoIntelligence className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap items-center gap-2 [&_button]:min-h-11 [&_a]:min-h-11">
              <AskGravitreSummonButton label={scopedDataset ? "Inspect this dataset" : section === "instructions" ? "Plan instructions" : "Plan training"} prompt={scopedDataset ? "Review the selected dataset’s grounding and preparation requirements. Distinguish reported readiness from missing evidence." : "Help me plan agent training using the available datasets and reported jobs."} />
              {!section ? (
                <Button variant="outline" size="sm" asChild>
                  <Link href={APP_ROUTES.builtInModels}>Built-in models</Link>
                </Button>
              ) : null}
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
            </div>
          }
        />
        ) : null}

        {loadError && (
          <WorkSectionErrorCard
            title="Could not load training"
            message={loadError}
            onRetry={() => {
              void ensureSelectedOrg(true)
                .then((orgId) => {
                  setOrgReady(Boolean(orgId))
                  setOrgError(
                    orgId
                      ? null
                      : "Organization membership required to load training data.",
                  )
                })
                .catch(() =>
                  setOrgError("Could not load your workspace. Try again."),
                )
              void mutateDatasets()
              void mutateJobs()
              void mutateInstructions()
              void mutateWorkflowAgents()
            }}
          />
        )}

        {agentFilterId && filteredAgent ? (
          <div className="rounded-[8px] border border-[color:var(--g-emerald)]/20 bg-[color:var(--g-emerald-pale)] px-4 py-3 text-sm flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span className="text-muted-foreground">
              Training knowledge for{" "}
              <span className="font-medium text-foreground">
                {filteredAgent.name}
              </span>
            </span>
            <div className="flex gap-2">
              <Button asChild variant="outline" size="sm" className="min-h-11">
                <Link href={`/agents/${agentFilterId}/knowledge`}>
                  RAG sources
                </Link>
              </Button>
              <Button asChild variant="ghost" size="sm" className="min-h-11">
                <Link href={embedded ? APP_ROUTES.intelligenceData : APP_ROUTES.training}>Clear filter</Link>
              </Button>
            </div>
          </div>
        ) : null}

        {(!section || section === "datasets") &&
        !loadError &&
        orgReady &&
        !trainingLoading &&
        datasets.length === 0 &&
        jobs.length === 0 &&
        instructions.length === 0 ? (
          <div className="rounded-[10px] border border-dashed border-[color:var(--g-emerald)]/25 bg-[color:var(--g-surface-2)] px-4 py-4 text-sm flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <span className="text-muted-foreground">
              {section === "datasets"
                ? "No datasets yet. Create one below or load starter examples."
                : "No training datasets, jobs, or instructions yet. Create a dataset below or load starter examples."}
            </span>
            <Button
              size="sm"
              variant="outline"
              className="border-[color:var(--g-emerald)]/30 hover:bg-[color:var(--g-emerald-pale)]"
              disabled={mutationPending || !orgReady}
              onClick={() => void handleCreateStarterDataset()}
            >
              {isCreatingStarter
                ? "Creating..."
                : starterDatasetId
                  ? "Retry starter import"
                  : "Load starter examples"}
            </Button>
          </div>
        ) : null}

        {!section ? (
        <TrainingOverview
          totalDatasets={datasetsData ? stats.totalDatasets : null}
          readyDatasets={datasetsData ? stats.readyDatasets : null}
          totalJobs={jobsData ? stats.totalJobs : null}
          activeJobs={jobsData ? stats.activeJobs : null}
          totalInstructions={instructionsData ? stats.totalInstructions : null}
        />
        ) : null}

        <div className="flex items-center justify-end">
          <DataFreshness
            updatedAt={trainingUpdatedAt}
            onRefresh={() => {
              void mutateDatasets()
              void mutateJobs()
              void mutateInstructions()
            }}
          />
        </div>

        {!section || section === "jobs" ? (
        <section
          aria-label="Training job monitor"
          className="space-y-2 border-b border-divide py-3"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-medium text-muted-foreground">
              Job monitor
            </p>
            <Button
              variant="ghost"
              size="sm"
              className="min-h-11 text-xs"
              onClick={() => setTrainingTab("jobs")}
              hidden={Boolean(section)}
            >
              Open jobs
            </Button>
          </div>
          <div className="grid grid-cols-2 gap-[var(--np-kpi-gap)] sm:grid-cols-4">
            <GravitreMetric
              label="Queued"
              value={jobsData ? stats.queuedJobs : "Not reported"}
            />
            <GravitreMetric
              label="Running"
              value={jobsData ? stats.runningJobs : "Not reported"}
            />
            <GravitreMetric
              label="Failed"
              value={jobsData ? stats.failedJobs : "Not reported"}
              warning={stats.failedJobs > 0}
            />
            <GravitreMetric
              label="Ready"
              value={jobsData ? stats.readyJobs : "Not reported"}
              hint="Completed jobs"
            />
          </div>
        </section>
        ) : null}

        {mutationError ? (
          <p
            role="alert"
            className="border-l-2 border-destructive pl-3 text-sm text-destructive"
          >
            {mutationError}
          </p>
        ) : null}
        <fieldset
          disabled={mutationPending || !orgReady}
          className="min-w-0 space-y-4 [&_button]:min-h-11 [&_input]:min-h-11 [&_select]:min-h-11 [&_label:has(input[type=file])]:min-h-11"
        >
          <Tabs
            value={trainingTab}
            onValueChange={setTrainingTab}
            className="space-y-4"
          >
            <nav
              hidden={Boolean(section)}
              aria-label="Training sections"
              className="mb-2 flex flex-wrap items-baseline gap-x-4 gap-y-1"
            >
              {(
                [
                  { id: "datasets", label: "Datasets" },
                  {
                    id: "jobs",
                    label:
                      stats.activeJobs > 0
                        ? `Jobs (${stats.activeJobs})`
                        : "Jobs",
                  },
                  { id: "instructions", label: "Instructions" },
                  { id: "models", label: "Fine-tunes" },
                ] as const
              ).map((item) => (
                <button
                  key={item.id}
                  type="button"
                  aria-pressed={trainingTab === item.id}
                  onClick={() => setTrainingTab(item.id)}
                  className={cn(
                    "text-xs underline-offset-4",
                    trainingTab === item.id
                      ? "text-[color:var(--g-text-primary)] underline"
                      : "text-[color:var(--g-text-muted)] hover:text-[color:var(--g-text-primary)]",
                  )}
                >
                  {item.label}
                </button>
              ))}
            </nav>

            <TabsContent value="datasets" className="mt-0 space-y-4">
              {datasetsLoading || !orgReady ? (
                <p role="status" className={TYPE.bodyMuted}>
                  Loading datasets…
                </p>
              ) : null}
              <div className="grid grid-cols-1 gap-6">
                <motion.section
                  initial={reduced ? false : { opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: reduced ? 0 : 0.2 }}
                  className="space-y-4 border-b border-divide pb-6"
                >
                  <div className="space-y-1">
                    <h2 className={TYPE.sectionTitle}>
                      {section === "datasets" ? "Create and edit datasets" : "Training datasets"}
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      Pick a type, add teaching material, then run a job when
                      you have enough records.
                    </p>
                  </div>

                  <div className="space-y-3 rounded-xl border border-border/50 bg-background/40 p-3">
                    <p className="text-xs font-medium text-muted-foreground">
                      Dataset type
                    </p>
                    <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
                      {DATASET_TYPE_META.map((meta) => {
                        const selected = datasetType === meta.value
                        return (
                          <button
                            key={meta.value}
                            type="button"
                            aria-pressed={selected}
                            onClick={() => setDatasetType(meta.value)}
                            className={cn(
                              "text-left text-sm underline-offset-4",
                              selected
                                ? "font-medium text-[color:var(--g-text-primary)] underline"
                                : "text-muted-foreground hover:text-foreground",
                            )}
                          >
                            {meta.label}
                          </button>
                        )
                      })}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {selectedTypeMeta.howToAdd} {selectedTypeMeta.trainHint}
                    </p>
                    <input
                      aria-label="Dataset name"
                      value={datasetName}
                      onChange={(event) => setDatasetName(event.target.value)}
                      placeholder={`${selectedTypeMeta.label} dataset name`}
                      className="w-full rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--g-brand)]/40"
                    />
                    <textarea
                      aria-label="Dataset description"
                      value={datasetDescription}
                      onChange={(event) =>
                        setDatasetDescription(event.target.value)
                      }
                      placeholder="What should this teach agents? (optional)"
                      className="min-h-16 w-full rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--g-brand)]/40"
                    />
                    <div className="flex flex-wrap gap-2">
                      <Button
                        onClick={() => void handleCreateDataset()}
                        disabled={isCreatingDataset || !datasetName.trim()}
                      >
                        {isCreatingDataset
                          ? "Creating..."
                          : `Create ${selectedTypeMeta.label} dataset`}
                      </Button>
                      {datasetType === "examples" && (
                        <Button
                          variant="outline"
                          disabled={mutationPending || !orgReady}
                          onClick={() => void handleCreateStarterDataset()}
                        >
                          {isCreatingStarter
                            ? "Creating..."
                            : starterDatasetId
                              ? "Retry starter import"
                              : "Load starter examples"}
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
                        const busy =
                          mutatingDatasetId === dataset.id ||
                          importingDatasetId === dataset.id
                        return (
                          <motion.div
                            key={dataset.id}
                            layout={!reduced}
                            initial={reduced ? false : { opacity: 0, y: 8 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={reduced ? undefined : { opacity: 0, y: -8 }}
                            transition={{ duration: reduced ? 0 : 0.18 }}
                            className="border-b border-divide py-3 last:border-b-0"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0 space-y-1">
                                <p className="font-medium text-foreground">
                                  {dataset.name}
                                </p>
                                <div className="flex flex-wrap items-center gap-1.5">
                                  <span className="rounded-md border border-border bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
                                    {typeMeta.label}
                                  </span>
                                  <span className="text-xs text-muted-foreground">
                                    {dataset.record_count ?? "Not reported"}{" "}
                                    record
                                    {dataset.record_count === 1
                                      ? ""
                                      : "s"} · {formatDate(dataset.created_at)}
                                  </span>
                                </div>
                                <p className="text-[11px] leading-relaxed text-muted-foreground">
                                  {typeMeta.summary}
                                </p>
                              </div>
                              <span
                                className={cn(
                                  "shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium",
                                  statusClasses(dataset.status),
                                )}
                              >
                                {dataset.status || "Not reported"}
                              </span>
                            </div>
                            {dataset.description ? (
                              <p className="mt-2 text-xs text-muted-foreground">
                                {dataset.description}
                              </p>
                            ) : null}

                            {isOpen && dataset.type === "examples" && (
                              <div className="mt-3 space-y-3 rounded-lg border border-border/60 bg-background/50 p-3">
                                <div className="grid grid-cols-1 gap-2">
                                  <textarea
                                    aria-label="Example input"
                                    value={recordInput}
                                    onChange={(event) =>
                                      setRecordInput(event.target.value)
                                    }
                                    placeholder="User / situation input"
                                    className="min-h-16 rounded-lg border border-border bg-background/80 px-3 py-2 text-sm"
                                  />
                                  <textarea
                                    aria-label="Expected output"
                                    value={recordOutput}
                                    onChange={(event) =>
                                      setRecordOutput(event.target.value)
                                    }
                                    placeholder="Ideal agent answer"
                                    className="min-h-16 rounded-lg border border-border bg-background/80 px-3 py-2 text-sm"
                                  />
                                  <div className="flex flex-wrap gap-2">
                                    <Button
                                      size="sm"
                                      onClick={() =>
                                        void handleAddRecord(dataset.id)
                                      }
                                      disabled={busy}
                                    >
                                      Save example
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => chooseMaterial(null)}
                                    >
                                      Cancel
                                    </Button>
                                  </div>
                                </div>
                                <div className="space-y-2 border-t border-border/50 pt-3">
                                  <p className="text-xs font-medium text-foreground">
                                    Bulk paste
                                  </p>
                                  <p className="text-[11px] text-muted-foreground">
                                    One pair per line: input =&gt; expected
                                    output (or tab-separated).
                                  </p>
                                  <textarea
                                    aria-label="Bulk examples"
                                    value={bulkText}
                                    onChange={(event) =>
                                      setBulkText(event.target.value)
                                    }
                                    placeholder={
                                      "What is our refund policy? => Refunds within 30 days...\nEscalate VIP tickets => Notify account owner within 15 minutes"
                                    }
                                    className="min-h-20 w-full rounded-lg border border-border bg-background/80 px-3 py-2 text-sm"
                                  />
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() =>
                                      void handleBulkExamples(dataset.id)
                                    }
                                    disabled={busy || !bulkText.trim()}
                                  >
                                    Import pasted examples
                                  </Button>
                                </div>
                              </div>
                            )}

                            {isOpen && dataset.type === "documents" && (
                              <div className="mt-3 space-y-3 rounded-lg border border-border/60 bg-background/50 p-3">
                                <p className="text-[11px] text-muted-foreground">
                                  {typeMeta.howToAdd}
                                </p>
                                <input
                                  aria-label="Document title"
                                  value={documentTitle}
                                  onChange={(event) =>
                                    setDocumentTitle(event.target.value)
                                  }
                                  placeholder="Document title (optional)"
                                  className="w-full rounded-lg border border-border bg-background/80 px-3 py-2 text-sm"
                                />
                                <textarea
                                  aria-label="Document text"
                                  value={documentBody}
                                  onChange={(event) =>
                                    setDocumentBody(event.target.value)
                                  }
                                  placeholder="Paste policy, playbook, or reference text..."
                                  className="min-h-28 w-full rounded-lg border border-border bg-background/80 px-3 py-2 text-sm"
                                />
                                <div className="flex flex-wrap items-center gap-2">
                                  <Button
                                    size="sm"
                                    onClick={() =>
                                      void handleImportDocument(dataset.id)
                                    }
                                    disabled={busy || !documentBody.trim()}
                                  >
                                    {importingDatasetId === dataset.id
                                      ? "Importing..."
                                      : "Import pasted text"}
                                  </Button>
                                  <label
                                    className={cn(
                                      "inline-flex h-8 cursor-pointer items-center justify-center rounded-md border border-input bg-background px-3 text-xs font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground",
                                      busy && "pointer-events-none opacity-50",
                                    )}
                                  >
                                    <input
                                      type="file"
                                      accept=".txt,.md,.markdown,text/plain"
                                      multiple
                                      className="sr-only"
                                      disabled={busy}
                                      onChange={(event) => {
                                        void handleImportDocumentFiles(
                                          dataset.id,
                                          event.target.files,
                                        )
                                        event.target.value = ""
                                      }}
                                    />
                                    {busy
                                      ? "Uploading..."
                                      : "Upload .txt / .md"}
                                  </label>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => chooseMaterial(null)}
                                  >
                                    Cancel
                                  </Button>
                                </div>
                              </div>
                            )}

                            {isOpen && dataset.type === "feedback" && (
                              <div className="mt-3 space-y-3 rounded-lg border border-border/60 bg-background/50 p-3">
                                <p className="text-[11px] text-muted-foreground">
                                  Pull helpful / not-helpful ratings from chat,
                                  or add a corrected example by hand.
                                </p>
                                <Button
                                  size="sm"
                                  onClick={() =>
                                    void handleImportFeedback(dataset.id)
                                  }
                                  disabled={busy}
                                >
                                  {importingDatasetId === dataset.id
                                    ? "Importing..."
                                    : "Import recent chat feedback"}
                                </Button>
                                <div className="grid grid-cols-1 gap-2 border-t border-border/50 pt-3">
                                  <textarea
                                    aria-label="Example input"
                                    value={recordInput}
                                    onChange={(event) =>
                                      setRecordInput(event.target.value)
                                    }
                                    placeholder="Original user message"
                                    className="min-h-16 rounded-lg border border-border bg-background/80 px-3 py-2 text-sm"
                                  />
                                  <textarea
                                    aria-label="Expected output"
                                    value={recordOutput}
                                    onChange={(event) =>
                                      setRecordOutput(event.target.value)
                                    }
                                    placeholder="Corrected / preferred answer"
                                    className="min-h-16 rounded-lg border border-border bg-background/80 px-3 py-2 text-sm"
                                  />
                                  <div className="flex flex-wrap gap-2">
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={() =>
                                        void handleAddRecord(dataset.id)
                                      }
                                      disabled={busy}
                                    >
                                      Save corrected example
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => chooseMaterial(null)}
                                    >
                                      Cancel
                                    </Button>
                                  </div>
                                </div>
                              </div>
                            )}

                            {isTraining && (
                              <div className="mt-3 space-y-2 rounded-lg border border-border/60 bg-background/50 p-3">
                                <p className="text-xs text-muted-foreground">
                                  Fine-tune a supported base model on this
                                  dataset (
                                  {dataset.record_count ?? "Not reported"}{" "}
                                  records). Progress appears under Training
                                  Jobs.
                                </p>
                                <div className="flex flex-wrap items-center gap-2">
                                  <select
                                    value={trainModelBase}
                                    onChange={(event) =>
                                      setTrainModelBase(event.target.value)
                                    }
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
                                    onClick={() =>
                                      void handleCreateJob(dataset.id)
                                    }
                                    disabled={
                                      busy ||
                                      !(
                                        typeof dataset.record_count ===
                                          "number" && dataset.record_count > 0
                                      )
                                    }
                                  >
                                    Start training job
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => setTrainDatasetId(null)}
                                  >
                                    Cancel
                                  </Button>
                                </div>
                              </div>
                            )}

                            <div className="mt-3 flex flex-wrap gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                className="hover:border-success/40 hover:text-success"
                                disabled={busy}
                                onClick={() => {
                                  chooseMaterial(isOpen ? null : dataset.id)
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
                                className="hover:border-info/40 hover:text-info"
                                disabled={
                                  busy ||
                                  !(
                                    typeof dataset.record_count === "number" &&
                                    dataset.record_count > 0
                                  )
                                }
                                onClick={() => {
                                  chooseMaterial(null)
                                  setTrainDatasetId(
                                    isTraining ? null : dataset.id,
                                  )
                                }}
                              >
                                Train
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                className="hover:border-destructive/40 hover:text-destructive"
                                disabled={busy}
                                onClick={() => {
                                  setMutationError(null)
                                  setDeleteTarget({
                                    kind: "dataset",
                                    id: dataset.id,
                                    name: dataset.name,
                                  })
                                }}
                              >
                                Delete
                              </Button>
                            </div>
                          </motion.div>
                        )
                      })}
                    </AnimatePresence>
                    {orgReady &&
                      !datasetsLoading &&
                      !datasetsError &&
                      datasetsData &&
                      datasets.length === 0 && (
                        <div className="rounded-xl border border-dashed border-border/70 px-4 py-6 text-center">
                          <p className="text-sm text-muted-foreground">
                            No datasets yet. Create one above, or load starter
                            examples to see the full flow.
                          </p>
                        </div>
                      )}
                  </div>
                </motion.section>
              </div>
            </TabsContent>

            <TabsContent value="jobs" className="mt-0 space-y-4">
              {jobsLoading || !orgReady ? (
                <p role="status" className={TYPE.bodyMuted}>
                  Loading jobs…
                </p>
              ) : null}
              <motion.section
                initial={reduced ? false : { opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: reduced ? 0 : 0.2 }}
                className="space-y-4 border-b border-divide pb-6"
              >
                <div className="space-y-1">
                  <h2 className={TYPE.sectionTitle}>Training jobs</h2>
                  <p className="text-sm text-muted-foreground">
                    Fine-tune runs started from a dataset. When a job completes,
                    assign the model under Fine-tunes.
                  </p>
                </div>
                <div className="space-y-2">
                  <AnimatePresence initial={false}>
                    {jobs.map((job) => {
                      const datasetLabel =
                        datasetNameById.get(job.dataset_id) ??
                        `Dataset ${job.dataset_id.slice(0, 8)}`
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
                          layout={!reduced}
                          initial={reduced ? false : { opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={reduced ? undefined : { opacity: 0, y: -8 }}
                          transition={{ duration: reduced ? 0 : 0.18 }}
                          className="border-b border-divide py-3 last:border-b-0"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="font-medium text-foreground">
                                {datasetLabel}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                Base {job.model_base || "Not reported"} ·{" "}
                                {formatDate(job.created_at)}
                              </p>
                              <p className="mt-1 text-[11px] text-muted-foreground">
                                {statusHint} ·{" "}
                                {reportedTrainingProgress(job.progress) == null
                                  ? "Progress not reported"
                                  : `${job.progress}%`}
                              </p>
                            </div>
                            <span
                              className={cn(
                                "shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium",
                                statusClasses(job.status),
                              )}
                            >
                              {job.status || "Not reported"}
                            </span>
                          </div>
                          {reportedTrainingProgress(job.progress) != null ? (
                            <div
                              role="progressbar"
                              aria-label={`Training progress for ${datasetLabel}`}
                              aria-valuenow={job.progress}
                              aria-valuemin={0}
                              aria-valuemax={100}
                              className="mt-3 h-1.5 overflow-hidden rounded-full bg-secondary"
                            >
                              <motion.div
                                className="relative h-full overflow-hidden bg-[color:var(--g-brand)]"
                                initial={false}
                                animate={{
                                  width: `${Math.max(0, Math.min(100, job.progress))}%`,
                                }}
                                transition={{ duration: reduced ? 0 : 0.2 }}
                              ></motion.div>
                            </div>
                          ) : null}
                          {job.status === "completed" ? (
                            <dl className="mt-3 grid grid-cols-2 gap-4 text-sm">
                              <div>
                                <dt className={TYPE.meta}>Reported accuracy</dt>
                                <dd>
                                  {typeof job.metrics?.accuracy === "number" &&
                                  Number.isFinite(job.metrics.accuracy)
                                    ? job.metrics.accuracy
                                    : "Not reported"}
                                </dd>
                              </div>
                              <div>
                                <dt className={TYPE.meta}>Reported loss</dt>
                                <dd>
                                  {typeof job.metrics?.loss === "number" &&
                                  Number.isFinite(job.metrics.loss)
                                    ? job.metrics.loss
                                    : "Not reported"}
                                </dd>
                              </div>
                            </dl>
                          ) : null}
                          {job.error ? (
                            <p
                              role="alert"
                              className="mt-2 text-sm text-destructive"
                            >
                              {job.error}
                            </p>
                          ) : null}
                          <AskGravitreSummonButton
                            selected={{ kind: "training-job", id: job.id, label: datasetLabel }}
                            label="Explain this job"
                            prompt="Explain this training job’s reported progress, errors and next useful action. Do not infer model readiness from completion alone."
                          />
                          {(job.status === "queued" ||
                            job.status === "training") && (
                            <div className="mt-3 flex gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                className="hover:border-destructive/40 hover:text-destructive"
                                disabled={mutatingJobId === job.id}
                                onClick={() => {
                                  setMutationError(null)
                                  setDeleteTarget({
                                    kind: "job",
                                    id: job.id,
                                    name: datasetLabel,
                                  })
                                }}
                              >
                                Cancel
                              </Button>
                            </div>
                          )}
                        </motion.div>
                      )
                    })}
                  </AnimatePresence>
                  {orgReady &&
                    !jobsLoading &&
                    !jobsError &&
                    jobsData &&
                    jobs.length === 0 && (
                      <div className="rounded-xl border border-dashed border-border/70 px-4 py-6 text-center">
                        <p className="text-sm text-muted-foreground">
                          No jobs yet. Add records to a dataset, then click
                          Train.
                        </p>
                      </div>
                    )}
                </div>
              </motion.section>
            </TabsContent>

            <TabsContent value="instructions" className="mt-0 space-y-6">
              {instructionsLoading ? (
                <p role="status" className={TYPE.bodyMuted}>
                  Loading instructions…
                </p>
              ) : null}
              {workflowAgentsError || agentsFallbackError ? (
                <WorkSectionErrorCard
                  title="Could not load instruction recipients"
                  message="Try again to refresh the agent roster."
                  onRetry={() => {
                    void mutateWorkflowAgents()
                    void mutateAgentsFallback()
                  }}
                />
              ) : null}
              <motion.section
                initial={reduced ? false : { opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: reduced ? 0 : 0.2 }}
                className="space-y-4 border-b border-divide pb-6"
              >
                <div className="space-y-1">
                  <h2 className={TYPE.sectionTitle}>Custom instructions</h2>
                  <p className="text-sm text-muted-foreground">
                    Live prompt guidance injected into agent chats when enabled.
                    Use this for tone, escalation rules, and standing policies
                    without waiting for a fine-tune.
                  </p>
                </div>
                <div className="grid grid-cols-1 gap-2 rounded-xl border border-border/50 bg-background/40 p-3">
                  <input
                    aria-label="Instruction name"
                    value={instructionName}
                    onChange={(event) => setInstructionName(event.target.value)}
                    placeholder="Instruction name (e.g. Escalation tone)"
                    className="rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--g-brand)]/40"
                  />
                  <select
                    value={effectiveSelectedAgentId}
                    onChange={(event) => setSelectedAgentId(event.target.value)}
                    disabled={
                      workflowAgentsLoading ||
                      agentsFallbackLoading ||
                      Boolean(workflowAgentsError || agentsFallbackError)
                    }
                    aria-label="Apply instruction to agent"
                    className="rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--g-brand)]/40"
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
                    aria-label="Instruction guidance"
                    value={instructionContent}
                    onChange={(event) =>
                      setInstructionContent(event.target.value)
                    }
                    placeholder="When enabled, this text is added to the agent system prompt (e.g. Always confirm before sending customer email)."
                    className="min-h-24 rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--g-brand)]/40"
                  />
                  <Button
                    onClick={() => void handleCreateInstruction()}
                    disabled={
                      isCreatingInstruction ||
                      !instructionName.trim() ||
                      !instructionContent.trim()
                    }
                  >
                    {isCreatingInstruction
                      ? "Creating..."
                      : "Create Instruction"}
                  </Button>
                </div>

                <div className="space-y-2">
                  <AnimatePresence initial={false}>
                    {visibleInstructions.map((instruction) => (
                      <motion.div
                        key={instruction.id}
                        layout={!reduced}
                        initial={reduced ? false : { opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={reduced ? undefined : { opacity: 0, y: -8 }}
                        transition={{ duration: reduced ? 0 : 0.18 }}
                        className="border-b border-divide py-3 last:border-b-0"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-medium text-foreground">
                              {instruction.name}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              Agent:{" "}
                              {instruction.agent_name ??
                                instruction.agent_id ??
                                "All"}{" "}
                              · Updated{" "}
                              {formatDate(
                                instruction.updated_at ||
                                  instruction.created_at,
                              )}
                            </p>
                          </div>
                          <span
                            className={cn(
                              "rounded-full border px-2 py-0.5 text-xs font-medium",
                              instruction.is_active
                                ? "bg-success/10 text-success border-success/20"
                                : "bg-secondary text-muted-foreground border-border",
                            )}
                          >
                            {typeof instruction.is_active === "boolean"
                              ? instruction.is_active
                                ? "active"
                                : "inactive"
                              : "Not reported"}
                          </span>
                        </div>
                        <p className="mt-2 text-sm text-muted-foreground whitespace-pre-wrap">
                          {instruction.content}
                        </p>
                        <div className="mt-3 flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            className="hover:border-info/40 hover:text-info"
                            disabled={mutatingInstructionId === instruction.id}
                            onClick={() =>
                              void handleToggleInstruction(instruction)
                            }
                          >
                            {instruction.is_active ? "Disable" : "Enable"}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="hover:border-destructive/40 hover:text-destructive"
                            disabled={mutatingInstructionId === instruction.id}
                            onClick={() => {
                              setMutationError(null)
                              setDeleteTarget({
                                kind: "instruction",
                                id: instruction.id,
                                name: instruction.name,
                              })
                            }}
                          >
                            Delete
                          </Button>
                        </div>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                  {orgReady &&
                    !instructionsLoading &&
                    !instructionsError &&
                    instructionsData &&
                    visibleInstructions.length === 0 && (
                      <p className="text-sm text-muted-foreground">
                        {agentFilterId
                          ? "No custom instructions for this agent yet."
                          : "No custom instructions yet."}
                      </p>
                    )}
                </div>
              </motion.section>
            </TabsContent>
            <TabsContent value="models" className="mt-0 space-y-6">
              {modelsError || workflowAgentsError || agentsFallbackError ? (
                <WorkSectionErrorCard
                  title="Could not load model assignment options"
                  message="Try again to refresh assignment options."
                  onRetry={() => {
                    void mutateModels()
                    void mutateWorkflowAgents()
                    void mutateAgentsFallback()
                  }}
                />
              ) : null}
              <motion.section
                initial={reduced ? false : { opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: reduced ? 0 : 0.2 }}
                className="space-y-4 border-b border-divide pb-6"
              >
                <h2 className={TYPE.sectionTitle}>Assign Fine-Tuned Models</h2>
                <p className="text-sm text-muted-foreground">
                  After a job completes, attach the model to a workflow agent.
                  Chat falls back to the agent base model if the fine-tuned
                  provider call fails.
                </p>
                {modelsLoading ? (
                  <p role="status" className={TYPE.bodyMuted}>
                    Loading fine-tuned models…
                  </p>
                ) : null}
                <div className="grid grid-cols-1 gap-2 rounded-xl border border-border/50 bg-background/40 p-3 md:grid-cols-2">
                  <select
                    value={effectiveAssignAgentId}
                    onChange={(event) => {
                      setAssignAgentId(event.target.value)
                      setAssignModelId(null)
                    }}
                    aria-label="Workflow agent"
                    className="rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--g-brand)]/40"
                  >
                    <option value="">
                      {workflowAgentsLoading || agentsFallbackLoading
                        ? "Loading agents…"
                        : "Choose an agent"}
                    </option>
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
                    className="rounded-lg border border-border bg-background/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[color:var(--g-brand)]/40"
                  >
                    <option value="">
                      {assignModelId === null &&
                      assignedModelForAgent === undefined
                        ? "Choose a model or use base model only"
                        : "Base model only (clear assignment)"}
                    </option>
                    {fineTunedModels.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.name} · v
                        {model.deployedVersion ??
                          model.currentVersion ??
                          "Not reported"}{" "}
                        · {model.status}
                      </option>
                    ))}
                  </select>
                  <Button
                    variant="outline"
                    disabled={isAssigningModel || !effectiveAssignAgentId}
                    onClick={() => setAssignModelId("")}
                  >
                    Use base model only
                  </Button>
                  <Button
                    className="md:col-span-2"
                    onClick={() => void handleAssignFineTunedModel()}
                    disabled={
                      isAssigningModel ||
                      !effectiveAssignAgentId ||
                      assignModelId === null ||
                      modelsLoading ||
                      workflowAgentsLoading ||
                      agentsFallbackLoading ||
                      Boolean(
                        modelsError ||
                          workflowAgentsError ||
                          agentsFallbackError,
                      )
                    }
                  >
                    {isAssigningModel ? "Saving..." : "Save Assignment"}
                  </Button>
                </div>
                {orgReady &&
                  !modelsLoading &&
                  !modelsError &&
                  fineTunedModelsData &&
                  fineTunedModels.length === 0 && (
                    <p className="text-sm text-muted-foreground">
                      No deployable fine-tuned models yet. Complete a
                      fine-tuning job first.
                    </p>
                  )}
                {assignableAgents.some((a) => a.trainedModelId) && (
                  <div className="space-y-2">
                    {assignableAgents
                      .filter((a) => a.trainedModelId)
                      .map((agent) => {
                        const model = fineTunedModels.find(
                          (m) => m.id === agent.trainedModelId,
                        )
                        return (
                          <div
                            key={agent.id}
                            className="border-b border-divide py-3 text-sm last:border-b-0"
                          >
                            <span className="font-medium text-foreground">
                              {agent.name}
                            </span>
                            <span className="text-muted-foreground">
                              {" "}
                              → {model?.name ?? agent.trainedModelId}
                              {model?.fineTunedOpenAiId
                                ? ` (${model.fineTunedOpenAiId})`
                                : ""}
                            </span>
                          </div>
                        )
                      })}
                  </div>
                )}
              </motion.section>
            </TabsContent>
          </Tabs>
        </fieldset>
        <Dialog
          open={Boolean(deleteTarget)}
          onOpenChange={(open) => {
            if (!open && !mutationRef.current) {
              setDeleteTarget(null)
              setMutationError(null)
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {deleteTarget?.kind === "job"
                  ? "Cancel training for"
                  : "Delete"}{" "}
                {deleteTarget?.name}?
              </DialogTitle>
              <DialogDescription>
                {deleteTarget?.kind === "dataset"
                  ? "This removes the dataset and its teaching material. Existing training history may still reference it."
                  : deleteTarget?.kind === "job"
                    ? "This requests cancellation of the training job. Your dataset and teaching material are retained."
                    : "This removes the instruction from agent guidance."}
              </DialogDescription>
            </DialogHeader>
            {mutationError ? (
              <p role="alert" className="text-sm text-destructive">
                {mutationError}
              </p>
            ) : null}
            <DialogFooter>
              <Button
                className="min-h-11"
                variant="outline"
                disabled={mutationPending}
                onClick={() => setDeleteTarget(null)}
              >
                {deleteTarget?.kind === "job"
                  ? "Keep training"
                  : `Keep ${deleteTarget?.kind}`}
              </Button>
              <Button
                className="min-h-11"
                variant="destructive"
                disabled={mutationPending}
                onClick={() => {
                  if (deleteTarget)
                    void (deleteTarget.kind === "dataset"
                      ? handleDeleteDataset(deleteTarget.id)
                      : deleteTarget.kind === "job"
                        ? handleCancelJob(deleteTarget.id)
                        : handleDeleteInstruction(deleteTarget.id))
                }}
              >
                {mutationPending
                  ? "Working…"
                  : deleteTarget?.kind === "job"
                    ? "Cancel job"
                    : "Delete"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
  )

  return embedded ? body : <AppShell title={pageTitle}>{body}</AppShell>
}
