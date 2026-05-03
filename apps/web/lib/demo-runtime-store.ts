type ApprovalStatus = "pending" | "approved" | "rejected"
type SessionStatus = "pending" | "running" | "completed"

type DemoApproval = {
  id: string
  title: string
  description: string
  type: "workflow" | "connector" | "config" | "access"
  environment: "production" | "staging"
  requestedBy: string
  requestedAt: string
  priority: "high" | "medium" | "low"
  status: ApprovalStatus
  context: {
    entity: string
    action: string
  }
}

type DemoTrainingDataset = {
  id: string
  name: string
  type: "examples" | "documents" | "feedback"
  description: string | null
  status: "ready" | "processing" | "failed"
  record_count: number
  created_at: string
  updated_at: string
}

type DemoTrainingJob = {
  id: string
  dataset_id: string
  model_base: string
  status: "queued" | "training" | "completed" | "failed" | "cancelled"
  progress: number
  created_at: string
  updated_at: string
}

type DemoInstruction = {
  id: string
  name: string
  content: string
  agent_id: string | null
  agent_name: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

type DemoSession = {
  id: string
  title: string
  status: SessionStatus
  environment: "production" | "staging"
  context_entity_type: "workflow" | "run" | "connector" | "source"
  context_entity_id: string
  created_at: string
}

type DemoStore = {
  approvals: DemoApproval[]
  training: {
    datasets: DemoTrainingDataset[]
    jobs: DemoTrainingJob[]
    instructions: DemoInstruction[]
  }
  sessions: DemoSession[]
}

declare global {
  // eslint-disable-next-line no-var
  var __gravitreDemoStore: DemoStore | undefined
}

function nowIso(): string {
  return new Date().toISOString()
}

function relativeFromIso(iso: string): string {
  const value = new Date(iso).getTime()
  if (Number.isNaN(value)) return "just now"
  const seconds = Math.max(0, Math.floor((Date.now() - value) / 1000))
  if (seconds < 60) return "just now"
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} minutes ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hours ago`
  const days = Math.floor(hours / 24)
  return `${days} days ago`
}

function buildDefaultStore(): DemoStore {
  const created = nowIso()
  return {
    approvals: [
      {
        id: "apr-001",
        title: "Retry failed sync-customers workflow",
        description: "Request to retry the failed workflow run that encountered a connection timeout",
        type: "workflow",
        environment: "production",
        requestedBy: "AI Operator",
        requestedAt: "5 minutes ago",
        priority: "high",
        status: "pending",
        context: { entity: "sync-customers-1234", action: "Retry workflow execution" },
      },
      {
        id: "apr-002",
        title: "Update Salesforce connector credentials",
        description: "OAuth token refresh required due to security policy rotation",
        type: "connector",
        environment: "production",
        requestedBy: "System",
        requestedAt: "15 minutes ago",
        priority: "high",
        status: "pending",
        context: { entity: "salesforce-api", action: "Update OAuth credentials" },
      },
    ],
    training: {
      datasets: [],
      jobs: [],
      instructions: [],
    },
    sessions: [
      {
        id: "sess-001",
        title: "Investigate connector timeout pattern",
        status: "running",
        environment: "production",
        context_entity_type: "connector",
        context_entity_id: "salesforce-api",
        created_at: created,
      },
    ],
  }
}

export function getDemoStore(): DemoStore {
  if (!globalThis.__gravitreDemoStore) {
    globalThis.__gravitreDemoStore = buildDefaultStore()
  }
  return globalThis.__gravitreDemoStore
}

export function addTrainingDataset(input: {
  name: string
  type: "examples" | "documents" | "feedback"
  description?: string
}): DemoTrainingDataset {
  const store = getDemoStore()
  const timestamp = nowIso()
  const dataset: DemoTrainingDataset = {
    id: `ds-${Date.now()}`,
    name: input.name,
    type: input.type,
    description: input.description ?? null,
    status: "ready",
    record_count: 0,
    created_at: timestamp,
    updated_at: timestamp,
  }
  store.training.datasets.unshift(dataset)
  return dataset
}

export function addTrainingJob(datasetId: string, modelBase: string): DemoTrainingJob {
  const store = getDemoStore()
  const timestamp = nowIso()
  const job: DemoTrainingJob = {
    id: `job-${Date.now()}`,
    dataset_id: datasetId,
    model_base: modelBase,
    status: "queued",
    progress: 0,
    created_at: timestamp,
    updated_at: timestamp,
  }
  store.training.jobs.unshift(job)
  return job
}

export function addInstruction(input: {
  name: string
  content: string
  agent_id?: string
}): DemoInstruction {
  const store = getDemoStore()
  const timestamp = nowIso()
  const instruction: DemoInstruction = {
    id: `ins-${Date.now()}`,
    name: input.name,
    content: input.content,
    agent_id: input.agent_id ?? null,
    agent_name: null,
    is_active: true,
    created_at: timestamp,
    updated_at: timestamp,
  }
  store.training.instructions.unshift(instruction)
  return instruction
}

export function addSession(title: string): DemoSession {
  const store = getDemoStore()
  const session: DemoSession = {
    id: `sess-${Date.now()}`,
    title,
    status: "pending",
    environment: "staging",
    context_entity_type: "workflow",
    context_entity_id: "new-task",
    created_at: nowIso(),
  }
  store.sessions.unshift(session)
  return session
}

export function setApprovalStatus(id: string, status: ApprovalStatus): DemoApproval | null {
  const store = getDemoStore()
  const target = store.approvals.find((item) => item.id === id)
  if (!target) return null
  target.status = status
  target.requestedAt = relativeFromIso(nowIso())
  return target
}
