/**
 * Typed API client for FastAPI backend
 * All methods include auth headers automatically via fetcher
 */

import { apiFetch, fetcher } from "@/lib/fetcher"
import { requestAgentInterrupt } from "@/lib/agent-interrupts"
import type {
  User,
  UserProfile,
  Organization,
  OperatorSummary,
  OperatorDetail,
  OperatorListResponse,
  OperatorSessionSummary,
  OperatorSessionDetail,
  OperatorSessionListResponse,
  OperatorSessionCreateRequest,
  OperatorActionPlanRequest,
  Agent,
  AgentMemory,
  AgentListResponse,
  CreateAgentRequest,
  Workflow,
  WorkflowListResponse,
  WorkflowNode,
  WorkflowEdge,
  WorkflowSchedule,
  ScheduledItem,
  SchedulesListParams,
  SchedulesListResponse,
  CreateWorkflowRequest,
  UpdateWorkflowRequest,
  Run,
  RunDetailResponse,
  RunListResponse,
  ExecuteWorkflowRequest,
  ExecuteWorkflowResponse,
  WorkflowDryRunResponse,
  ApproveRejectRequest,
  Connector,
  ConnectorListResponse,
  CreateConnectorRequest,
  CreateFederationHandoffRequest,
  CreateFederationConnectorGrantRequest,
  CreateFederationDelegatedTaskRequest,
  Source,
  SourceListResponse,
  CreateSourceRequest,
  DataSourceTypesResponse,
  DataSourceTestResponse,
  DataSourceQueryResponse,
  SourceSyncHistoryItem,
  SourceConnectorOption,
  SourceDetail,
  SearchResponse,
  SearchHistoryItem,
  Conversation,
  ConversationMessage,
  TrainingDatasetType,
  TrainingDataset,
  TrainingJob,
  CustomInstruction,
  TrainingDatasetListResponse,
  TrainingJobListResponse,
  CustomInstructionListResponse,
  FineTunedModelListResponse,
  WorkflowAgentListResponse,
  AgentFineTunedModelAssignment,
  AuditLog,
  AuditListResponse,
  AuditSummary,
  Subscription,
  Invoice,
  BillingOverview,
  ApiKey,
  ApiKeyListResponse,
  BillingUsageResponse,
  LiteSeatsResponse,
  MesonAddonsResponse,
  NotificationListResponse,
  OnboardingProgress,
  LiteTask,
  LiteDeliverable,
  LiteHomeData,
  LiteResultsSummary,
  SSOConfiguration,
  SSOConfigurationCreate,
  SSOInitResponse,
  MetricsOverview,
  MetricInsight,
  MarketplaceRegistryConnector,
  MarketplaceBillingStatus,
  MarketplaceAssetPayoutSummary,
  MarketplacePublisherPayoutSyncResult,
  MarketplacePublisherRevenueAnalytics,
  MarketplacePartnerPricing,
  MarketplaceAnalyticsSummary,
  MarketplaceAssetCheckoutResult,
  MarketplaceAssetEntitlementStatus,
  MarketplaceCategoriesResponse,
  MarketplaceFederatedConnectorSummary,
  MarketplaceRoiSummary,
  MarketplaceReviewsResponse,
  MarketplaceSavesListResponse,
  MarketplaceAssetCloneResult,
  MarketplaceAssetDetail,
  MarketplaceAssetInstallCheck,
  MarketplaceAssetInstallResult,
  MarketplaceAssetsListResponse,
  MarketplacePublisherProfile,
  MarketplaceInstallBlocker,
  MarketplaceInstallsListResponse,
  FederationPartnership,
  FederationHandoff,
  FederationConnectorGrant,
  FederationDelegatedTask,
  AgentInterrupt,
  AgentInterruptRequest,
  MarketplaceSandboxDemoResult,
  MarketplaceSandboxProvisionResult,
  MarketplaceSandboxStatus,
  PartnerConnectorSubmission,
  PartnerSecurityChecklist,
  EnterpriseDataRegion,
  EnterpriseBranding,
  EnterpriseDomainInstructions,
  EnterpriseDomainVerifyResult,
  EnterpriseWorkforceAnalytics,
  EnterpriseCostAttribution,
  EnterpriseSiemConfig,
  EnterpriseSiemTestResult,
  PrivateConnectorBundle,
  IntegrationHealthScore,
  IntegrationHealthSnapshot,
  IntegrationHealthHistoryResponse,
  IntegrationSuggestion,
  IntegrationSuggestionsResponse,
  IntegrationSuggestionScanResponse,
  IntegrationSuggestionApplyResponse,
  PlatformCsWorkspaceResponse,
  PlatformCsAlertsResponse,
  PlatformCsEscalateResponse,
  PlatformCsSnapshotBackfillResponse,
  PlatformCsTenantQueueActionResponse,
  WorkflowFailureAlert,
  WorkflowFailureAlertsResponse,
  WorkflowFailurePredictionScanResponse,
  OrgFailurePredictionScanResponse,
  KnowledgeSyncJob,
  KnowledgeSyncJobsResponse,
  KnowledgeSyncTriggerResponse,
  WorkflowDigitalTwinResponse,
  ResumeGraphRunRequest,
  ApprovalBatchView,
  ApprovalBatchDecideRequest,
  RunCompensationSummary,
  AutonomousRunBudgetLimits,
  AutonomousRunBudgetUsage,
  EnterpriseAutonomousRunBudgets,
  EnterpriseHipaaStatus,
  EnterpriseTransparencyLogsResponse,
  EnterpriseTransparencyExport,
  AgentSwarmRun,
  AgentSwarmListResponse,
  AgentSwarmStartRequest,
  MlModelDetail,
  MlModelListResponse,
  MlModelSummary,
  CreateMlModelRequest,
  MlModelType,
  MlPredictRequest,
  MlPredictResponse,
} from "@/types/api"

// Base URL for backend API (can be overridden via env).
// Paths passed to apiUrl() always start with /api/… — when NEXT_PUBLIC_API_URL ends
// with /api, strip the duplicate segment so production does not hit /api/api/….
const API_BASE = process.env.NEXT_PUBLIC_API_URL || ""

if (typeof window !== "undefined") {
  const base = API_BASE.trim().replace(/\/+$/, "")
  if (
    base &&
    !base.startsWith("/") &&
    !base.startsWith(window.location.origin)
  ) {
    console.warn(
      "[Gravitre] NEXT_PUBLIC_API_URL bypasses the Next.js BFF. Leave it unset so /api/* routes proxy through the web app with auth and org headers.",
    )
  }
}

function apiUrl(path: string): string {
  const base = API_BASE.trim().replace(/\/+$/, "")
  if (!base) return path
  if (path.startsWith("/api/") && base.endsWith("/api")) {
    return `${base}${path.slice(4)}`
  }
  return `${base}${path}`
}

function extractErrorMessage(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") return null
  const data = payload as Record<string, unknown>

  const detail = data.detail
  if (typeof detail === "string" && detail.trim()) return detail
  if (detail && typeof detail === "object") {
    const detailObj = detail as Record<string, unknown>
    const nestedDetail = detailObj.detail
    if (typeof nestedDetail === "string" && nestedDetail.trim()) return nestedDetail
    const detailMessage = detailObj.message
    if (typeof detailMessage === "string" && detailMessage.trim()) return detailMessage
    const activeRunId = detailObj.active_run_id
    if (typeof activeRunId === "string" && activeRunId.trim()) {
      return `Workflow already has an active run (${activeRunId.slice(0, 8)}…). Open Runs to monitor it.`
    }
  }
  if (Array.isArray(detail)) {
    const first = detail[0]
    if (first && typeof first === "object") {
      const msg = (first as Record<string, unknown>).msg
      if (typeof msg === "string" && msg.trim()) return msg
    }
  }

  const details = data.details
  if (details && typeof details === "object") {
    const detailsObj = details as Record<string, unknown>
    const detailsMessage = detailsObj.message ?? detailsObj.reason
    if (typeof detailsMessage === "string" && detailsMessage.trim()) return detailsMessage
  }

  const error = data.error
  if (typeof error === "string" && error.trim()) return error
  if (error && typeof error === "object") {
    const errorObj = error as Record<string, unknown>
    const nested = errorObj.message ?? errorObj.detail
    if (typeof nested === "string" && nested.trim()) return nested
  }

  const message = data.message
  if (typeof message === "string" && message.trim()) return message
  return null
}

export class ApiRequestError extends Error {
  status: number
  payload: unknown

  constructor(message: string, status: number, payload: unknown) {
    super(message)
    this.name = "ApiRequestError"
    this.status = status
    this.payload = payload
  }
}

function unwrapAgent(payload: unknown): Agent {
  if (payload && typeof payload === "object" && "agent" in payload) {
    return (payload as { agent: Agent }).agent
  }
  return payload as Agent
}

async function postJson<T>(url: string, data: unknown): Promise<T> {
  const response = await apiFetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new ApiRequestError(
      extractErrorMessage(error) || `Request failed: ${response.status}`,
      response.status,
      error,
    )
  }
  return response.json()
}

async function patchJson<T>(url: string, data: unknown): Promise<T> {
  const response = await apiFetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new ApiRequestError(
      extractErrorMessage(error) || `Request failed: ${response.status}`,
      response.status,
      error,
    )
  }
  return response.json()
}

async function deleteJson<T>(url: string): Promise<T> {
  const response = await apiFetch(url, { method: "DELETE" })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(extractErrorMessage(error) || `Request failed: ${response.status}`)
  }
  return response.json()
}

async function putJson<T>(url: string, data: unknown): Promise<T> {
  const response = await apiFetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(extractErrorMessage(error) || `Request failed: ${response.status}`)
  }
  return response.json()
}

async function deleteRequest(url: string): Promise<void> {
  const response = await apiFetch(url, { method: "DELETE" })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(extractErrorMessage(error) || `Request failed: ${response.status}`)
  }
}

async function postNoContent(url: string, data?: unknown): Promise<void> {
  const response = await apiFetch(url, {
    method: "POST",
    headers: data ? { "Content-Type": "application/json" } : undefined,
    body: data ? JSON.stringify(data) : undefined,
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(extractErrorMessage(error) || `Request failed: ${response.status}`)
  }
}

// ============ Auth ============
export const authApi = {
  me: () => fetcher<UserProfile>(apiUrl("/api/auth/me")),
  updateProfile: (data: Partial<User>) => patchJson<User>(apiUrl("/api/auth/me"), data),
  changePassword: (currentPassword: string, newPassword: string) =>
    postJson<void>(apiUrl("/api/auth/change-password"), {
      current_password: currentPassword,
      new_password: newPassword,
    }),
  listSessions: () =>
    fetcher<{
      sessions: { id: string; device: string; ip: string; last_active: string; current: boolean }[]
    }>(apiUrl("/api/auth/sessions")),
  revokeSession: (sessionId: string) => deleteRequest(apiUrl(`/api/auth/sessions/${sessionId}`)),
  revokeAllSessions: () => postJson<void>(apiUrl("/api/auth/sessions/revoke-all"), {}),
  uploadAvatar: async (file: File) => {
    const formData = new FormData()
    formData.append("avatar", file)
    const response = await apiFetch(apiUrl("/api/auth/avatar"), {
      method: "POST",
      body: formData,
    })
    if (!response.ok) throw new Error("Upload failed")
    return response.json() as Promise<{ avatar_url: string }>
  },
  removeAvatar: () => deleteRequest(apiUrl("/api/auth/avatar")),
}

// ============ Operators ============
export const operatorsApi = {
  list: () => fetcher<OperatorListResponse>(apiUrl("/api/operators")),
  get: (id: string) => fetcher<OperatorDetail>(apiUrl(`/api/operators/${id}`)),
  create: (data: { name: string; description?: string }) =>
    postJson<OperatorDetail>(apiUrl("/api/operators"), data),
  update: (id: string, data: Partial<OperatorSummary>) =>
    patchJson<OperatorDetail>(apiUrl(`/api/operators/${id}`), data),
  delete: (id: string) => deleteRequest(apiUrl(`/api/operators/${id}`)),
  
  // Sessions
  listSessions: (operatorId: string) =>
    fetcher<OperatorSessionListResponse>(apiUrl(`/api/operators/${operatorId}/sessions`)),
  getSession: (operatorId: string, sessionId: string) =>
    fetcher<OperatorSessionDetail>(apiUrl(`/api/operators/${operatorId}/sessions/${sessionId}`)),
  createSession: (operatorId: string, data: OperatorSessionCreateRequest) =>
    postJson<OperatorSessionSummary>(apiUrl(`/api/operators/${operatorId}/sessions`), data),
  
  // AI Planning
  createPlan: (operatorId: string, data: OperatorActionPlanRequest) =>
    postJson<{ plan_id: string; title: string; summary: string; steps: unknown[] }>(
      apiUrl(`/api/operators/${operatorId}/plan`),
      data
    ),
  executePlan: (operatorId: string, data: { session_id: string; plan_id: string; step_id: string }) =>
    postJson<{ action_id: string; status: string }>(apiUrl(`/api/operators/${operatorId}/run`), data),
}

// ============ Agents ============
export const agentsApi = {
  list: () => fetcher<AgentListResponse>(apiUrl("/api/agents")),
  get: async (id: string) => unwrapAgent(await fetcher<unknown>(apiUrl(`/api/agents/${id}`))),
  create: async (data: CreateAgentRequest) => unwrapAgent(await postJson<unknown>(apiUrl("/api/agents"), data)),
  update: async (id: string, data: Partial<Agent>) =>
    unwrapAgent(await patchJson<unknown>(apiUrl(`/api/agents/${id}`), data)),
  delete: (id: string) => deleteRequest(apiUrl(`/api/agents/${id}`)),
  start: async (id: string) => unwrapAgent(await postJson<unknown>(apiUrl(`/api/agents/${id}/start`), {})),
  stop: async (id: string) => unwrapAgent(await postJson<unknown>(apiUrl(`/api/agents/${id}/stop`), {})),
  listMemories: (agentId: string, params?: { category?: string; q?: string }) => {
    const search = new URLSearchParams()
    if (params?.category) search.set("category", params.category)
    if (params?.q) search.set("q", params.q)
    const query = search.toString()
    return fetcher<AgentMemory[]>(
      apiUrl(`/api/agents/${agentId}/memories${query ? `?${query}` : ""}`)
    )
  },
  createMemory: (agentId: string, data: Partial<AgentMemory> & { content: string }) =>
    postJson<AgentMemory>(apiUrl(`/api/agents/${agentId}/memories`), data),
  updateMemory: (agentId: string, memoryId: string, data: Partial<AgentMemory>) =>
    patchJson<AgentMemory>(apiUrl(`/api/agents/${agentId}/memories/${memoryId}`), data),
  deleteMemory: (agentId: string, memoryId: string) =>
    deleteRequest(apiUrl(`/api/agents/${agentId}/memories/${memoryId}`)),
  searchMemories: (agentId: string, data: { query: string; topK?: number; category?: string }) =>
    postJson<AgentMemory[]>(apiUrl(`/api/agents/${agentId}/memories/search`), data),
}

export interface AgentKnowledgeAssignment {
  id?: string
  agentId?: string
  sourceType: string
  sourceId: string
  label: string
  includeRules?: string[]
  excludeRules?: string[]
  syncFrequency?: string
  syncEnabled?: boolean
  freshnessStatus?: string
  lastSyncedAt?: string | null
  enabled?: boolean
  fromConfig?: boolean
}

export interface AgentCapabilityProfile {
  agentId: string
  capabilities?: string[]
  allowedConnectors?: string[]
  canExecuteWithApproval?: boolean
  connectedKnowledgeSources: Array<{ label?: string; sourceType?: string; freshnessStatus?: string }>
  availableReadActions: string[]
  availableWriteActions: string[]
  approvalRequiredActions: string[]
  learningSources: string[]
  memoryCount: number
  freshnessStatus: string
  confidenceScore: number
}

export const agentKnowledgeApi = {
  listAssignments: (agentId: string) =>
    fetcher<{ assignments: AgentKnowledgeAssignment[] }>(
      apiUrl(`/api/agents/${agentId}/knowledge-assignments`)
    ),
  createAssignment: (agentId: string, data: Partial<AgentKnowledgeAssignment> & { sourceType: string; sourceId: string; label: string }) =>
    postJson<AgentKnowledgeAssignment>(apiUrl(`/api/agents/${agentId}/knowledge-assignments`), data),
  updateAssignment: (agentId: string, assignmentId: string, data: Partial<AgentKnowledgeAssignment>) =>
    patchJson<AgentKnowledgeAssignment>(
      apiUrl(`/api/agents/${agentId}/knowledge-assignments/${assignmentId}`),
      data
    ),
  deleteAssignment: (agentId: string, assignmentId: string) =>
    deleteRequest(apiUrl(`/api/agents/${agentId}/knowledge-assignments/${assignmentId}`)),
  syncAssignment: (agentId: string, assignmentId: string) =>
    postJson<{ success: boolean; message?: string }>(
      apiUrl(`/api/agents/${agentId}/knowledge-assignments/${assignmentId}/sync`),
      {}
    ),
  getCapabilities: (agentId: string) =>
    fetcher<AgentCapabilityProfile>(apiUrl(`/api/agents/${agentId}/capabilities`)),
  getMemoryLineage: (agentId: string) =>
    fetcher<{ lineage: Array<Record<string, unknown>> }>(apiUrl(`/api/agents/${agentId}/memory-lineage`)),
  testRetrieval: (agentId: string, query: string) =>
    postJson<{ matchCount: number; sources: Array<Record<string, unknown>> }>(
      apiUrl(`/api/agents/${agentId}/knowledge-assignments/test-retrieval`),
      { query }
    ),
  listDemoWorkflows: () =>
    fetcher<{ workflows: Array<Record<string, unknown>> }>(apiUrl("/api/agents/demo-knowledge-workflows")),
}

// ============ Meson ============
export interface MesonInterpretResponse {
  intent: string
  department: string
  systems: string[]
  outputTypes: string[]
  generatedConfig: {
    agent: string
    agent_role?: string
    agent_description?: string
    training: string[]
    workflows: string[]
    sample_outputs: string[]
  }
  confidence?: number
  explanation?: string
}

export interface MesonDeployResponse {
  agentId: string
  workflowId?: string | null
  result: MesonInterpretResponse
}

export interface MesonSuggestion {
  id: string
  nodeType: string
  label: string
  reason?: string
  confidence?: number
}

export interface MesonSuggestionsResponse {
  suggestions: MesonSuggestion[]
}

export interface MesonAlert {
  id: string
  severity: "info" | "warning" | "critical" | string
  title: string
  message: string
  autoFixable?: boolean
  actionType?: "navigate" | string
  actionTarget?: string
  fixLabel?: string
}

export interface MesonAlertsResponse {
  alerts: MesonAlert[]
}

export interface MesonInsight {
  id: string
  title: string
  summary: string
  category?: string
}

export interface MesonInsightsResponse {
  insights: MesonInsight[]
}

export interface MesonPageContextResponse {
  insights: MesonInsight[]
  suggestions: MesonSuggestion[]
  source?: string | null
}

export interface MesonFeedbackRequest {
  suggestionId: string
  action: "accepted" | "dismissed"
  reason?: string
  workflowId?: string
}

export interface MesonPreferencesResponse {
  department?: string | null
  systems?: string[]
  outputTypes?: string[]
  preferredBuildHoursUtc?: number[]
  interpretCount?: number
  deployCount?: number
}

export interface MesonFeedbackMetricsResponse {
  acceptedCount?: number
  dismissedCount?: number
  acceptanceRate?: number | null
  suggestions?: Array<{
    suggestionId: string
    accepted: number
    dismissed: number
    acceptanceRate?: number | null
  }>
}

export const mesonApi = {
  interpret: (data: {
    intent: string
    department: string
    systems: string[]
    outputTypes: string[]
  }) => postJson<MesonInterpretResponse>(apiUrl("/api/meson/interpret"), data),
  deploy: (data: {
    intent: string
    department: string
    systems: string[]
    outputTypes: string[]
    generatedConfig?: MesonInterpretResponse["generatedConfig"]
    createWorkflow?: boolean
  }) => postJson<MesonDeployResponse>(apiUrl("/api/meson/deploy"), data),
  suggestions: (data: {
    workflowState?: Record<string, unknown>
    lastAddedNode?: Record<string, unknown>
    workflowId?: string
  }) =>
    postJson<MesonSuggestionsResponse>(apiUrl("/api/meson/suggestions"), data),
  alerts: () => fetcher<MesonAlertsResponse>(apiUrl("/api/meson/alerts")),
  insights: () => fetcher<MesonInsightsResponse>(apiUrl("/api/meson/insights")),
  pageContext: (params: { page: string; entityId?: string }) => {
    const search = new URLSearchParams({ page: params.page })
    if (params.entityId) search.set("entity_id", params.entityId)
    return fetcher<MesonPageContextResponse>(apiUrl(`/api/meson/page-context?${search}`))
  },
  optimizations: (workflowId: string) =>
    fetcher<MesonInsightsResponse>(apiUrl(`/api/meson/optimizations/${workflowId}`)),
  preferences: () => fetcher<MesonPreferencesResponse>(apiUrl("/api/meson/preferences")),
  feedbackMetrics: (workflowId?: string) =>
    fetcher<MesonFeedbackMetricsResponse>(
      apiUrl(
        `/api/meson/feedback/metrics${workflowId ? `?workflowId=${encodeURIComponent(workflowId)}` : ""}`
      )
    ),
  feedback: (data: MesonFeedbackRequest) =>
    postJson<{ ok?: boolean }>(apiUrl("/api/meson/feedback"), data),
}

// ============ Workflows ============
export const workflowsApi = {
  list: () => fetcher<WorkflowListResponse>(apiUrl("/api/workflows")),
  get: async (id: string) => {
    const payload = await fetcher<Workflow | { workflow: Workflow }>(apiUrl(`/api/workflows/${id}`))
    if (payload && typeof payload === "object" && "workflow" in payload && payload.workflow) {
      return payload.workflow
    }
    return payload as Workflow
  },
  create: (data: CreateWorkflowRequest) => postJson<Workflow>(apiUrl("/api/workflows"), data),
  update: (id: string, data: UpdateWorkflowRequest) =>
    patchJson<Workflow>(apiUrl(`/api/workflows/${id}`), data),
  delete: (id: string) => deleteRequest(apiUrl(`/api/workflows/${id}`)),
  
  // Nodes
  listNodes: (workflowId: string, versionId?: string) =>
    fetcher<{ nodes: WorkflowNode[] }>(
      apiUrl(`/api/workflows/${workflowId}/nodes${versionId ? `?version_id=${versionId}` : ""}`)
    ),
  createNode: (workflowId: string, data: Partial<WorkflowNode>) =>
    postJson<WorkflowNode>(apiUrl(`/api/workflows/${workflowId}/nodes`), data),
  updateNode: (workflowId: string, nodeId: string, data: Partial<WorkflowNode>) =>
    patchJson<WorkflowNode>(apiUrl(`/api/workflows/${workflowId}/nodes/${nodeId}`), data),
  deleteNode: (workflowId: string, nodeId: string) =>
    deleteRequest(apiUrl(`/api/workflows/${workflowId}/nodes/${nodeId}`)),
  
  // Edges
  listEdges: (workflowId: string, versionId?: string) =>
    fetcher<{ edges: WorkflowEdge[] }>(
      apiUrl(`/api/workflows/${workflowId}/edges${versionId ? `?version_id=${versionId}` : ""}`)
    ),
  createEdge: (workflowId: string, data: Partial<WorkflowEdge>) =>
    postJson<WorkflowEdge>(apiUrl(`/api/workflows/${workflowId}/edges`), data),
  deleteEdge: (workflowId: string, edgeId: string) =>
    deleteRequest(apiUrl(`/api/workflows/${workflowId}/edges/${edgeId}`)),
  
  // Versions
  listVersions: (workflowId: string) =>
    fetcher<{ versions: Workflow["versions"] }>(apiUrl(`/api/workflows/${workflowId}/versions`)),
  activateVersion: (workflowId: string, versionId: string) =>
    postJson<void>(apiUrl(`/api/workflows/${workflowId}/versions/${versionId}/activate`), {}),
  
  // Schedules
  listSchedules: (workflowId: string) =>
    fetcher<{ schedules: WorkflowSchedule[] }>(apiUrl(`/api/workflows/${workflowId}/schedules`)),
  createSchedule: (workflowId: string, data: { cron_expression: string; enabled?: boolean }) =>
    postJson<WorkflowSchedule>(apiUrl(`/api/workflows/${workflowId}/schedules`), data),
  updateSchedule: (workflowId: string, scheduleId: string, data: Partial<WorkflowSchedule>) =>
    patchJson<WorkflowSchedule>(apiUrl(`/api/workflows/${workflowId}/schedules/${scheduleId}`), data),
  deleteSchedule: (workflowId: string, scheduleId: string) =>
    deleteRequest(apiUrl(`/api/workflows/${workflowId}/schedules/${scheduleId}`)),
  
  getBuilder: (workflowId: string) =>
    fetcher<{ workflow_id: string; name?: string; nodes: WorkflowNode[]; edges: WorkflowEdge[] }>(
      apiUrl(`/api/workflows/${workflowId}/builder`)
    ),
  saveBuilder: (workflowId: string, data: { nodes: unknown[]; edges: unknown[]; name?: string; description?: string }) =>
    apiFetch(apiUrl(`/api/workflows/${workflowId}/builder`), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then(async (response) => {
      if (!response.ok) {
        const error = await response.json().catch(() => ({}))
        throw new Error(extractErrorMessage(error) || `Request failed: ${response.status}`)
      }
      return response.json()
    }),

  // Execution
  execute: (data: ExecuteWorkflowRequest) =>
    postJson<ExecuteWorkflowResponse>(apiUrl("/api/workflows/execute"), data),
  dryRun: (data: { workflow_id?: string; definition?: unknown; parameters?: unknown }) =>
    postJson<WorkflowDryRunResponse>(apiUrl("/api/workflows/dry-run"), data),

  // Predictive failure alerts (STA-122)
  listFailurePredictions: (params?: { workflowId?: string; status?: string }) => {
    const query = new URLSearchParams()
    if (params?.workflowId) query.set("workflowId", params.workflowId)
    if (params?.status) query.set("status", params.status)
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<WorkflowFailureAlertsResponse>(apiUrl(`/api/workflows/failure-predictions${suffix}`))
  },
  dismissFailurePrediction: (alertId: string) =>
    postJson<{ alert: WorkflowFailureAlert }>(
      apiUrl(`/api/workflows/failure-predictions/${alertId}/dismiss`),
      {},
    ),
  scanFailurePredictions: (workflowId: string) =>
    postJson<WorkflowFailurePredictionScanResponse>(
      apiUrl(`/api/workflows/${workflowId}/failure-predictions/scan`),
      {},
    ),
  scanAllFailurePredictions: () =>
    postJson<OrgFailurePredictionScanResponse>(
      apiUrl("/api/workflows/failure-predictions/scan"),
      {},
    ),
  digitalTwin: (data: { workflow_id?: string; definition?: unknown; parameters?: unknown }) =>
    postJson<WorkflowDigitalTwinResponse>(apiUrl("/api/workflows/digital-twin"), data),
  resumeRun: (runId: string, data: ResumeGraphRunRequest) =>
    postJson<{ run_id: string; status: string; steps?: Record<string, unknown>[] }>(
      apiUrl(`/api/workflows/runs/${runId}/resume`),
      data,
    ),
  getApprovalBatch: (runId: string) =>
    fetcher<{ batch: ApprovalBatchView | null }>(apiUrl(`/api/workflows/runs/${runId}/approval-batch`)),
  decideApprovalBatch: (runId: string, data: ApprovalBatchDecideRequest) =>
    postJson<{ batch: ApprovalBatchView; status?: string; run_id?: string }>(
      apiUrl(`/api/workflows/runs/${runId}/approval-batch/decide`),
      data,
    ),
}

// ============ Schedules dashboard ============
export const schedulesApi = {
  list: (params?: SchedulesListParams) => {
    const query = new URLSearchParams()
    if (params?.workflowId) query.set("workflow_id", params.workflowId)
    if (params?.from) query.set("from", params.from)
    if (params?.to) query.set("to", params.to)
    if (params?.kinds?.length) query.set("kinds", params.kinds.join(","))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<SchedulesListResponse>(apiUrl(`/api/schedules${suffix}`))
  },
}

// ============ Runs ============
export const runsApi = {
  list: (filters?: { status?: string; workflow_id?: string; limit?: number; offset?: number }) => {
    const params = new URLSearchParams()
    if (filters?.status) params.set("status", filters.status)
    if (filters?.workflow_id) params.set("workflow_id", filters.workflow_id)
    if (filters?.limit) params.set("limit", String(filters.limit))
    if (filters?.offset) params.set("offset", String(filters.offset))
    const query = params.toString()
    return fetcher<RunListResponse>(apiUrl(`/api/runs${query ? `?${query}` : ""}`))
  },
  get: (id: string) => fetcher<Run>(apiUrl(`/api/runs/${id}`)),
  getWithSteps: (id: string) => fetcher<RunDetailResponse>(apiUrl(`/api/runs/${id}`)),
  cancel: async (id: string) => {
    await requestAgentInterrupt("workflow_run", id, "cancel")
    return { success: true, interrupt: "cancel" as const }
  },
  pause: async (id: string) => {
    await requestAgentInterrupt("workflow_run", id, "pause")
    return { success: true, interrupt: "pause" as const }
  },
  retry: (id: string) => postJson<Run>(apiUrl(`/api/runs/${id}/retry`), {}),
  retryStep: (runId: string, stepId: string) =>
    postJson<{ success?: boolean; status?: string }>(apiUrl(`/api/runs/${runId}/steps/${stepId}/retry`), {}),
  resumePaused: (id: string) =>
    postJson<{ success?: boolean; status?: string }>(apiUrl(`/api/runs/${id}/resume-paused`), {}),
  rollback: (id: string) =>
    postJson<{ run_id?: string; status?: string }>(apiUrl(`/api/runs/${id}/rollback`), {}),
  compensate: (id: string) => postJson<RunCompensationSummary>(apiUrl(`/api/runs/${id}/compensate`), {}),
  interrupt: (id: string, signal: AgentInterruptRequest["signal"]) =>
    requestAgentInterrupt("workflow_run", id, signal).then((interrupt) => ({ interrupt })),
}

// ============ Agent interrupts (STA-108) ============
export const agentInterruptsApi = {
  request: (data: AgentInterruptRequest) =>
    requestAgentInterrupt(data.targetType, data.targetId, data.signal).then((interrupt) => ({ interrupt })),
}

// ============ Marketplace ============
export const marketplaceApi = {
  listRegistry: () =>
    fetcher<{ connectors: MarketplaceRegistryConnector[] }>(apiUrl("/api/marketplace/registry")),
  listSubmissions: (status?: string) => {
    const query = status ? `?status=${encodeURIComponent(status)}` : ""
    return fetcher<{ submissions: PartnerConnectorSubmission[] }>(
      apiUrl(`/api/marketplace/submissions${query}`)
    )
  },
  listMySubmissions: (status?: string) => {
    const query = status ? `?status=${encodeURIComponent(status)}` : ""
    return fetcher<{ submissions: PartnerConnectorSubmission[] }>(
      apiUrl(`/api/marketplace/submissions/mine${query}`)
    )
  },
  submit: (data: {
    manifest: Record<string, unknown>
    securityChecklist: PartnerSecurityChecklist
    packageSources?: Record<string, string>
  }) => postJson<{ submission: PartnerConnectorSubmission }>(apiUrl("/api/marketplace/submissions"), data),
  rescan: (id: string) =>
    postJson<{ submission: PartnerConnectorSubmission }>(
      apiUrl(`/api/marketplace/submissions/${id}/rescan`),
      {}
    ),
  listPrivateBundles: () =>
    fetcher<{ bundles: PrivateConnectorBundle[] }>(apiUrl("/api/marketplace/private-bundles")),
  uploadPrivateBundle: (data: {
    name: string
    manifest: Record<string, unknown>
    packageSources: Record<string, string>
    signingPublicKeyPem: string
    signature: string
  }) => postJson<{ bundle: PrivateConnectorBundle }>(apiUrl("/api/marketplace/private-bundles"), data),
  activatePrivateBundle: (id: string) =>
    postJson<{ bundle: PrivateConnectorBundle }>(
      apiUrl(`/api/marketplace/private-bundles/${id}/activate`),
      {}
    ),
  disablePrivateBundle: (id: string) =>
    postJson<{ bundle: PrivateConnectorBundle }>(
      apiUrl(`/api/marketplace/private-bundles/${id}/disable`),
      {}
    ),
  review: (id: string, data: { decision: "approve" | "reject"; notes?: string }) =>
    postJson<{
      submission: PartnerConnectorSubmission
      registry: MarketplaceRegistryConnector | null
    }>(apiUrl(`/api/marketplace/submissions/${id}/review`), data),
  sandboxStatus: () => fetcher<MarketplaceSandboxStatus>(apiUrl("/api/marketplace/sandbox")),
  provisionSandbox: () =>
    postJson<MarketplaceSandboxProvisionResult>(apiUrl("/api/marketplace/sandbox"), {}),
  resetSandbox: () =>
    postJson<MarketplaceSandboxProvisionResult>(apiUrl("/api/marketplace/sandbox/reset"), {}),
  runSandboxDemo: () =>
    postJson<MarketplaceSandboxDemoResult>(apiUrl("/api/marketplace/sandbox/demo"), {}),
  billingStatus: () => fetcher<MarketplaceBillingStatus>(apiUrl("/api/marketplace/billing/status")),
  connectOnboard: (data: { returnUrl: string; refreshUrl: string }) =>
    postJson<{ url: string; expiresAt?: number }>(
      apiUrl("/api/marketplace/billing/connect/onboard"),
      data
    ),
  syncConnectAccount: () =>
    postJson<{ account: MarketplaceBillingStatus["account"] }>(
      apiUrl("/api/marketplace/billing/connect/sync"),
      {}
    ),
  listPricing: () =>
    fetcher<{ pricing: MarketplacePartnerPricing[] }>(apiUrl("/api/marketplace/billing/pricing")),
  upsertPricing: (
    registryId: string,
    data: { pricingModel: "free" | "flat_monthly" | "per_invocation"; priceCents: number; currency?: string }
  ) =>
    putJson<{ pricing: MarketplacePartnerPricing }>(
      apiUrl(`/api/marketplace/billing/pricing/${registryId}`),
      data
    ),

  // Unified marketplace assets (MKT-5 / MKT-6)
  listAssets: (params?: {
    assetType?: string
    category?: string
    department?: string
    pricingType?: string
    visibility?: string
    featured?: boolean
    search?: string
    limit?: number
    offset?: number
  }) => {
    const query = new URLSearchParams()
    if (params?.assetType) query.set("assetType", params.assetType)
    if (params?.category) query.set("category", params.category)
    if (params?.department) query.set("department", params.department)
    if (params?.pricingType) query.set("pricingType", params.pricingType)
    if (params?.visibility) query.set("visibility", params.visibility)
    if (params?.featured) query.set("featured", "true")
    if (params?.search) query.set("search", params.search)
    if (params?.limit != null) query.set("limit", String(params.limit))
    if (params?.offset != null) query.set("offset", String(params.offset))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<MarketplaceAssetsListResponse>(apiUrl(`/api/marketplace/assets${suffix}`))
  },
  getAsset: (assetRef: string) =>
    fetcher<{ asset: MarketplaceAssetDetail }>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}`),
    ),
  installCheck: (assetRef: string) =>
    fetcher<MarketplaceAssetInstallCheck>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}/install-check`),
    ),
  installAsset: (assetRef: string, installVariables?: Record<string, string>) =>
    postJson<MarketplaceAssetInstallResult>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}/install`),
      installVariables ? { installVariables } : {},
    ),
  cloneAsset: (assetRef: string) =>
    postJson<MarketplaceAssetCloneResult>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}/clone`),
      {},
    ),
  listCategories: () => fetcher<MarketplaceCategoriesResponse>(apiUrl("/api/marketplace/categories")),
  analyticsSummary: () =>
    fetcher<MarketplaceAnalyticsSummary>(apiUrl("/api/marketplace/analytics/summary")),
  analyticsRoi: (params?: { limit?: number }) => {
    const query = new URLSearchParams()
    if (params?.limit != null) query.set("limit", String(params.limit))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<MarketplaceRoiSummary>(apiUrl(`/api/marketplace/analytics/roi${suffix}`))
  },
  listFederatedConnectors: (params?: { search?: string; limit?: number; offset?: number }) => {
    const query = new URLSearchParams()
    if (params?.search) query.set("search", params.search)
    if (params?.limit != null) query.set("limit", String(params.limit))
    if (params?.offset != null) query.set("offset", String(params.offset))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<{ assets: MarketplaceFederatedConnectorSummary[]; total: number }>(
      apiUrl(`/api/marketplace/federated-connectors${suffix}`),
    )
  },
  assetEntitlement: (assetRef: string) =>
    fetcher<MarketplaceAssetEntitlementStatus>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}/entitlement`),
    ),
  assetCheckout: (assetRef: string, data: { successUrl: string; cancelUrl: string }) =>
    postJson<MarketplaceAssetCheckoutResult>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}/checkout`),
      data,
    ),
  syncPublisherPayouts: () =>
    postJson<{
      sync: MarketplacePublisherPayoutSyncResult
      summary: MarketplaceAssetPayoutSummary
    }>(apiUrl("/api/marketplace/publisher/payouts/sync"), {}),
  publisherRevenueAnalytics: () =>
    fetcher<MarketplacePublisherRevenueAnalytics>(apiUrl("/api/marketplace/publisher/analytics")),
  listAssetReviews: (assetRef: string, params?: { limit?: number; offset?: number }) => {
    const query = new URLSearchParams()
    if (params?.limit != null) query.set("limit", String(params.limit))
    if (params?.offset != null) query.set("offset", String(params.offset))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<MarketplaceReviewsResponse>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}/reviews${suffix}`),
    )
  },
  upsertAssetReview: (
    assetRef: string,
    data: { rating: number; title?: string; body?: string },
  ) =>
    putJson<{ review: import("@/types/api").MarketplaceReview }>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}/reviews/mine`),
      data,
    ),
  deleteAssetReview: (assetRef: string) =>
    deleteJson<{ deleted: boolean; assetId: string }>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}/reviews/mine`),
    ),
  saveAsset: (assetRef: string) =>
    postJson<{ saved: boolean }>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}/save`),
      {},
    ),
  unsaveAsset: (assetRef: string) =>
    deleteJson<{ saved: boolean }>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}/save`),
    ),
  listSaves: (params?: { limit?: number; offset?: number }) => {
    const query = new URLSearchParams()
    if (params?.limit != null) query.set("limit", String(params.limit))
    if (params?.offset != null) query.set("offset", String(params.offset))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<MarketplaceSavesListResponse>(apiUrl(`/api/marketplace/saves${suffix}`))
  },
  listInstalls: (params?: { status?: string; assetId?: string; limit?: number; offset?: number }) => {
    const query = new URLSearchParams()
    if (params?.status) query.set("status", params.status)
    if (params?.assetId) query.set("assetId", params.assetId)
    if (params?.limit != null) query.set("limit", String(params.limit))
    if (params?.offset != null) query.set("offset", String(params.offset))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<MarketplaceInstallsListResponse>(apiUrl(`/api/marketplace/installs${suffix}`))
  },
  listOrgAssets: (params?: { status?: string; reviewScope?: string; limit?: number; offset?: number }) => {
    const query = new URLSearchParams()
    if (params?.status) query.set("status", params.status)
    if (params?.reviewScope) query.set("reviewScope", params.reviewScope)
    if (params?.limit != null) query.set("limit", String(params.limit))
    if (params?.offset != null) query.set("offset", String(params.offset))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<MarketplaceAssetsListResponse>(apiUrl(`/api/marketplace/org/assets${suffix}`))
  },
  createOrgAsset: (body: {
    slug: string
    title: string
    assetType: "ai_agent" | "workflow" | "knowledge_pack" | "department_pack" | "connector_config"
    config: Record<string, unknown>
    description?: string
    category?: string
    department?: string
    tags?: string[]
    businessOutcome?: string
    useCase?: string
    estimatedHoursSaved?: number
    pricingType?: "free" | "paid" | "subscription"
    priceCents?: number
  }) =>
    postJson<{ created: boolean; asset: MarketplaceAssetDetail }>(
      apiUrl("/api/marketplace/assets"),
      body,
    ),
  submitAssetForReview: (assetRef: string) =>
    postJson<{ submitted: boolean; asset: MarketplaceAssetDetail }>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}/submit-for-review`),
      {},
    ),
  approveOrgAsset: (assetRef: string) =>
    postJson<{ approved: boolean; asset: MarketplaceAssetDetail }>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}/approve`),
      {},
    ),
  updateOrgAsset: (
    assetRef: string,
    body: {
      slug?: string
      title?: string
      description?: string
      category?: string
      department?: string
      tags?: string[]
      config?: Record<string, unknown>
      businessOutcome?: string
      useCase?: string
      estimatedHoursSaved?: number
      pricingType?: "free" | "paid" | "subscription"
      priceCents?: number
      currency?: string
    },
  ) =>
    patchJson<{ updated: boolean; asset: MarketplaceAssetDetail }>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}`),
      body,
    ),
  updateOrgAssetPricing: (
    assetRef: string,
    body: { pricingType: "free" | "paid" | "subscription"; priceCents: number; currency?: string },
  ) =>
    patchJson<{ updated: boolean; asset: MarketplaceAssetDetail }>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}/pricing`),
      body,
    ),
  archiveOrgAsset: (assetRef: string) =>
    deleteJson<{ archived: boolean; asset: MarketplaceAssetDetail }>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}`),
    ),
  listAssetVersions: (assetRef: string) =>
    fetcher<{
      assetId: string
      slug?: string
      currentVersion: number
      versions: {
        versionNumber: number
        changeSummary?: string | null
        publishedAt?: string | null
        publishedBy?: string | null
        isCurrent: boolean
      }[]
    }>(apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}/versions`)),
  rollbackAssetVersion: (assetRef: string, version: number) =>
    postJson<{
      rolledBack: boolean
      assetId: string
      slug?: string
      previousVersion: number
      currentVersion: number
      restoredFromVersion: number
    }>(apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}/rollback`), { version }),
  rejectOrgAsset: (assetRef: string, reason: string) =>
    postJson<{ rejected: boolean; reason: string; asset: MarketplaceAssetDetail }>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}/reject`),
      { reason },
    ),
  uninstallAsset: (assetRef: string) =>
    postJson<{ uninstalled: boolean; installId: string; assetId: string; slug?: string }>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}/uninstall`),
      {},
    ),
  getPublisherProfile: () =>
    fetcher<{ publisher: MarketplacePublisherProfile | null }>(apiUrl("/api/marketplace/publisher/me")),
  onboardPublisher: (body: {
    displayName: string
    slug?: string
    description?: string
    websiteUrl?: string
    logoUrl?: string
  }) => postJson<{ onboarded: boolean; publisher: MarketplacePublisherProfile }>(
    apiUrl("/api/marketplace/publisher/onboard"),
    body,
  ),
  submitAssetForPublicReview: (assetRef: string) =>
    postJson<{ submitted: boolean; asset: MarketplaceAssetDetail }>(
      apiUrl(`/api/marketplace/assets/${encodeURIComponent(assetRef)}/submit-for-public-review`),
      {},
    ),
  listPlatformReviewQueue: (params?: { limit?: number; offset?: number }) => {
    const query = new URLSearchParams()
    if (params?.limit != null) query.set("limit", String(params.limit))
    if (params?.offset != null) query.set("offset", String(params.offset))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<MarketplaceAssetsListResponse>(apiUrl(`/api/marketplace/platform/review-queue${suffix}`))
  },
  getPlatformReviewAsset: (assetRef: string) =>
    fetcher<{ asset: MarketplaceAssetDetail }>(
      apiUrl(`/api/marketplace/platform/assets/${encodeURIComponent(assetRef)}/review`),
    ),
  listPlatformCatalog: (params?: {
    featured?: boolean
    verified?: boolean
    search?: string
    limit?: number
    offset?: number
  }) => {
    const query = new URLSearchParams()
    if (params?.featured) query.set("featured", "true")
    if (params?.verified) query.set("verified", "true")
    if (params?.search) query.set("search", params.search)
    if (params?.limit != null) query.set("limit", String(params.limit))
    if (params?.offset != null) query.set("offset", String(params.offset))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<MarketplaceAssetsListResponse>(apiUrl(`/api/marketplace/platform/catalog${suffix}`))
  },
  approvePlatformAsset: (assetRef: string) =>
    postJson<{ approved: boolean; asset: MarketplaceAssetDetail }>(
      apiUrl(`/api/marketplace/platform/assets/${encodeURIComponent(assetRef)}/approve`),
      {},
    ),
  rejectPlatformAsset: (assetRef: string, reason: string) =>
    postJson<{ rejected: boolean; reason: string; asset: MarketplaceAssetDetail }>(
      apiUrl(`/api/marketplace/platform/assets/${encodeURIComponent(assetRef)}/reject`),
      { reason },
    ),
  setPlatformAssetFeatured: (assetRef: string, enabled: boolean) =>
    postJson<{ featured: boolean; asset: MarketplaceAssetDetail }>(
      apiUrl(`/api/marketplace/platform/assets/${encodeURIComponent(assetRef)}/featured`),
      { enabled },
    ),
  setPlatformAssetVerified: (assetRef: string, enabled: boolean) =>
    postJson<{ verified: boolean; asset: MarketplaceAssetDetail }>(
      apiUrl(`/api/marketplace/platform/assets/${encodeURIComponent(assetRef)}/verified`),
      { enabled },
    ),
  updatePlatformAssetPricing: (
    assetRef: string,
    body: { pricingType: "free" | "paid" | "subscription"; priceCents: number; currency?: string },
  ) =>
    patchJson<{ updated: boolean; asset: MarketplaceAssetDetail }>(
      apiUrl(`/api/marketplace/platform/assets/${encodeURIComponent(assetRef)}/pricing`),
      body,
    ),
}

// ============ Approvals ============
export const approvalsApi = {
  list: () => fetcher<{ approvals: Run[] }>(apiUrl("/api/approvals")),
  approve: (runId: string, data?: ApproveRejectRequest) =>
    postJson<Run>(apiUrl(`/api/approvals/${runId}/approve`), data || {}),
  reject: (runId: string, data?: ApproveRejectRequest) =>
    postJson<Run>(apiUrl(`/api/approvals/${runId}/reject`), data || {}),
}

// ============ Connectors ============
export const connectorsApi = {
  list: () => fetcher<ConnectorListResponse>(apiUrl("/api/connectors")),
  actionCatalog: () =>
    fetcher<import("@/lib/connector-actions").ConnectorActionCatalogResponse>(
      apiUrl("/api/connectors/catalog/actions")
    ),
  actionCatalogForVendor: (vendor: string) =>
    fetcher<import("@/lib/connector-actions").VendorActionCatalog>(
      apiUrl(`/api/connectors/catalog/actions/${encodeURIComponent(vendor)}`)
    ),
  get: (id: string) => fetcher<Connector>(apiUrl(`/api/connectors/${id}`)),
  create: (data: CreateConnectorRequest) => postJson<Connector>(apiUrl("/api/connectors"), data),
  update: (id: string, data: Partial<Connector>) =>
    patchJson<Connector>(apiUrl(`/api/connectors/${id}`), data),
  delete: (id: string, confirmName: string) =>
    postJson<void>(apiUrl(`/api/connectors/${id}/delete`), { confirmName }),
  sync: (id: string, fullSync?: boolean) =>
    postJson<{ status: string }>(apiUrl(`/api/connectors/${id}/sync`), { fullSync }),
  testConnection: (id: string) =>
    postJson<{ success: boolean; message?: string }>(apiUrl(`/api/connectors/${id}/test`), {}),
  startOAuth: (
    provider: string,
    data: {
      name: string
      connectorId?: string
      redirectPath?: string
      subdomain?: string
      instanceUrl?: string
      tenantUrl?: string
      tenant?: string
      munchkinId?: string
      owner?: string
      repo?: string
    }
  ) =>
    postJson<{ authorizationUrl: string; connectorId: string; state: string }>(
      apiUrl(`/api/connectors/oauth/${provider}/start`),
      data
    ),
  reconnectOAuth: (
    provider: string,
    connectorId: string,
    name: string,
    extra?: { subdomain?: string; instanceUrl?: string; owner?: string; repo?: string }
  ) =>
    postJson<{ authorizationUrl: string; connectorId: string; state: string }>(
      apiUrl(`/api/connectors/oauth/${provider}/start`),
      { name, connectorId, redirectPath: "/connectors", ...extra }
    ),
  listGoogleAnalyticsProperties: (connectorId: string) =>
    fetcher<{
      connectorId: string
      properties: Array<{
        property_id: string
        property_resource?: string
        display_name?: string
        account_name?: string
      }>
      linkedPropertyId?: string
      linkedPropertyName?: string
    }>(apiUrl(`/api/connectors/${connectorId}/google-analytics/properties`)),
  linkGoogleAnalyticsProperty: (
    connectorId: string,
    data: { propertyId: string; propertyName?: string }
  ) =>
    putJson<{ connectorId: string; propertyId: string; propertyName?: string; status: string }>(
      apiUrl(`/api/connectors/${connectorId}/google-analytics/property`),
      data
    ),
  listGoogleSearchConsoleSites: (connectorId: string) =>
    fetcher<{
      connectorId: string
      sites: Array<{ site_url: string; permission_level?: string }>
      linkedSiteUrl?: string
      linkedPermissionLevel?: string
    }>(apiUrl(`/api/connectors/${connectorId}/google-search-console/sites`)),
  linkGoogleSearchConsoleSite: (
    connectorId: string,
    data: { siteUrl: string; permissionLevel?: string }
  ) =>
    putJson<{ connectorId: string; siteUrl: string; permissionLevel?: string; status: string }>(
      apiUrl(`/api/connectors/${connectorId}/google-search-console/site`),
      data
    ),
}

// ============ Sources ============
export const sourcesApi = {
  list: () => fetcher<SourceListResponse>(apiUrl("/api/sources")),
  listTypes: (params?: { category?: string; search?: string }) => {
    const query = new URLSearchParams()
    if (params?.category) query.set("category", params.category)
    if (params?.search) query.set("search", params.search)
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<DataSourceTypesResponse>(apiUrl(`/api/sources/types${suffix}`))
  },
  listConnectors: (vendor: string) =>
    fetcher<{ connectors: SourceConnectorOption[] }>(apiUrl(`/api/sources/connectors?vendor=${encodeURIComponent(vendor)}`)),
  get: (id: string) => fetcher<{ source: SourceDetail }>(apiUrl(`/api/sources/${id}`)),
  create: (data: CreateSourceRequest) => postJson<{ id: string; typeId?: string }>(apiUrl("/api/sources"), data),
  update: (id: string, data: Partial<Source>) => patchJson<Source>(apiUrl(`/api/sources/${id}`), data),
  delete: (id: string) => deleteRequest(apiUrl(`/api/sources/${id}`)),
  sync: (id: string) => postJson<{ status: string; tables?: number; records?: number }>(apiUrl(`/api/sources/${id}/sync`), {}),
  testConnection: (data: { typeId: string; config?: Record<string, unknown>; connectionString?: string }) =>
    postJson<DataSourceTestResponse>(apiUrl("/api/sources/test"), data),
  testExisting: (id: string) => postJson<DataSourceTestResponse>(apiUrl(`/api/sources/${id}/test`), {}),
  getSchema: (id: string) => fetcher<{ tables: unknown[]; tableCount: number }>(apiUrl(`/api/sources/${id}/schema`)),
  getSyncHistory: (id: string) => fetcher<{ history: SourceSyncHistoryItem[] }>(apiUrl(`/api/sources/${id}/sync-history`)),
  query: (id: string, question: string) =>
    postJson<DataSourceQueryResponse>(apiUrl(`/api/sources/${id}/query`), { question }),
}

// ============ Search ============
export const searchApi = {
  search: (query: string, filters?: { types?: string[]; dateRange?: string }) =>
    postJson<SearchResponse>(apiUrl("/api/search"), { query, filters }),
  history: () => fetcher<{ searches: SearchHistoryItem[] }>(apiUrl("/api/search/history")),
  deleteHistory: (id: string) => deleteRequest(apiUrl(`/api/search/history/${id}`)),
  clearHistory: () => deleteRequest(apiUrl("/api/search/history")),
}

// ============ Conversations ============
export const conversationsApi = {
  list: (params?: { search?: string; includeArchived?: boolean; limit?: number; offset?: number }) => {
    const query = new URLSearchParams()
    if (params?.search) query.set("search", params.search)
    if (params?.includeArchived) query.set("include_archived", "true")
    if (params?.limit) query.set("limit", String(params.limit))
    if (params?.offset) query.set("offset", String(params.offset))
    const qs = query.toString()
    return fetcher<{ conversations: Conversation[] }>(apiUrl(`/api/conversations${qs ? `?${qs}` : ""}`))
  },
  get: (id: string) => fetcher<Conversation>(apiUrl(`/api/conversations/${id}`)),
  create: (data: { title?: string }) => postJson<Conversation>(apiUrl("/api/conversations"), data),
  update: (id: string, data: { title?: string }) => patchJson<Conversation>(apiUrl(`/api/conversations/${id}`), data),
  archive: (id: string) => postJson<Conversation>(apiUrl(`/api/conversations/${id}/archive`), {}),
  delete: (id: string) => deleteRequest(apiUrl(`/api/conversations/${id}`)),
  bulkDelete: (ids: string[]) => postNoContent(apiUrl("/api/conversations/bulk-delete"), { ids }),
  getMessages: (id: string) => fetcher<{ messages: ConversationMessage[] }>(apiUrl(`/api/conversations/${id}/messages`)),
  appendMessages: (id: string, messages: Array<{ role: "user" | "assistant"; content: string; tool_calls?: unknown[] }>) =>
    postJson<{ messages: ConversationMessage[] }>(apiUrl(`/api/conversations/${id}/messages`), { messages }),
}

export const assistantApi = {
  dailyBriefing: () =>
    fetcher<{
      greeting: string
      bullets: Array<string | { id?: string; text: string; href?: string; tone?: "error" | "success" | "warning" }>
      suggestions: string[]
    }>(apiUrl("/api/assistant/daily-briefing")),
  orgContext: () =>
    fetcher<{
      counts: { agents: number; workflows: number; connectors: number }
      agents: Array<{ id: string; name: string }>
      workflows: Array<{ id: string; name: string }>
      connectors: Array<{ id: string; name: string; type?: string }>
    }>(apiUrl("/api/assistant/org-context")),
  getPreferences: () =>
    fetcher<{ preferred_model?: string | null; preferred_mode?: string; preferred_persona?: string | null }>(
      apiUrl("/api/assistant/preferences"),
    ),
  updatePreferences: (data: { preferred_model?: string; preferred_mode?: string; preferred_persona?: string }) =>
    patchJson<{ preferred_model?: string | null; preferred_mode?: string; preferred_persona?: string | null }>(
      apiUrl("/api/assistant/preferences"),
      data,
    ),
  getConversationState: (conversationId: string) =>
    fetcher<{ task_state: Record<string, unknown> }>(apiUrl(`/api/assistant/conversation/${conversationId}/state`)),
  executeConversationTask: (conversationId: string) =>
    postJson<{
      success: boolean
      message: string
      execution_result?: {
        success?: boolean
        entity_type?: string
        entity_id?: string
        connector_management_url?: string | null
        result_url?: string | null
        integration?: string | null
        title?: string
        body?: string
        task_label?: string
      }
      task_state?: Record<string, unknown>
    }>(apiUrl(`/api/assistant/conversation/${conversationId}/execute`), { confirm: true }),
  submitFeedback: (data: {
    message_id: string
    helpful: boolean
    reason?: string
    corrected_answer?: string
  }) => postJson<{ status: string }>(apiUrl("/api/assistant/feedback"), data),
  businessSignals: (department?: string) =>
    fetcher<{ signals: Array<Record<string, unknown>>; collected_at?: string }>(
      apiUrl(`/api/assistant/business-signals${department ? `?department=${encodeURIComponent(department)}` : ""}`),
    ),
  advisorBrief: (params?: { department?: string; query?: string }) => {
    const search = new URLSearchParams()
    if (params?.department) search.set("department", params.department)
    if (params?.query) search.set("query", params.query)
    const qs = search.toString()
    return fetcher<Record<string, unknown>>(
      apiUrl(`/api/assistant/advisor-brief${qs ? `?${qs}` : ""}`),
    )
  },
  executiveAdvisorBrief: () =>
    fetcher<Record<string, unknown>>(apiUrl("/api/assistant/advisor-brief/executive")),
  recommendationFeedback: (data: { recommendation_id: string; accepted: boolean; department?: string }) =>
    postJson<{ status: string }>(apiUrl("/api/assistant/recommendation-feedback"), data),
}

// ============ Training ============
export const trainingApi = {
  // Datasets
  listDatasets: () => fetcher<TrainingDatasetListResponse>(apiUrl("/api/training/datasets")),
  getDataset: (id: string) => fetcher<TrainingDataset>(apiUrl(`/api/training/datasets/${id}`)),
  createDataset: (data: { name: string; type: TrainingDatasetType; description?: string }) =>
    postJson<TrainingDataset>(apiUrl("/api/training/datasets"), data),
  deleteDataset: (id: string) => deleteRequest(apiUrl(`/api/training/datasets/${id}`)),
  uploadRecords: (datasetId: string, records: { input: string; expected_output: string }[]) =>
    postJson<{ added: number }>(apiUrl(`/api/training/datasets/${datasetId}/records`), { records }),

  // Jobs
  listJobs: () => fetcher<TrainingJobListResponse>(apiUrl("/api/training/jobs")),
  getJob: (id: string) => fetcher<TrainingJob>(apiUrl(`/api/training/jobs/${id}`)),
  createJob: (datasetId: string, modelBase: string) =>
    postJson<TrainingJob>(apiUrl("/api/training/jobs"), { dataset_id: datasetId, model_base: modelBase }),
  cancelJob: (id: string) => postJson<void>(apiUrl(`/api/training/jobs/${id}/cancel`), {}),

  // Instructions
  listInstructions: () => fetcher<CustomInstructionListResponse>(apiUrl("/api/training/instructions")),
  getInstruction: (id: string) => fetcher<CustomInstruction>(apiUrl(`/api/training/instructions/${id}`)),
  createInstruction: (data: { name: string; content: string; agent_id?: string }) =>
    postJson<CustomInstruction>(apiUrl("/api/training/instructions"), data),
  updateInstruction: (id: string, data: Partial<CustomInstruction>) =>
    patchJson<CustomInstruction>(apiUrl(`/api/training/instructions/${id}`), data),
  deleteInstruction: (id: string) => deleteRequest(apiUrl(`/api/training/instructions/${id}`)),
  toggleInstruction: (id: string, isActive: boolean) =>
    patchJson<CustomInstruction>(apiUrl(`/api/training/instructions/${id}`), { is_active: isActive }),

  // Fine-tuned model → agent runtime (STA-99)
  listWorkflowAgents: () => fetcher<WorkflowAgentListResponse>(apiUrl("/api/training/workflow-agents")),
  listFineTunedModels: () => fetcher<FineTunedModelListResponse>(apiUrl("/api/training/fine-tuned-models")),
  getAgentFineTunedModel: (agentId: string) =>
    fetcher<AgentFineTunedModelAssignment>(apiUrl(`/api/training/agents/${agentId}/fine-tuned-model`)),
  assignAgentFineTunedModel: (agentId: string, trainedModelId: string | null) =>
    putJson<AgentFineTunedModelAssignment>(apiUrl(`/api/training/agents/${agentId}/fine-tuned-model`), {
      trainedModelId,
    }),
}

function normalizeMlModel(raw: Record<string, unknown>): MlModelSummary {
  return {
    id: String(raw.id ?? ""),
    name: String(raw.name ?? "Model"),
    description: (raw.description as string | null | undefined) ?? null,
    modelType: String(raw.model_type ?? raw.modelType ?? "classifier") as MlModelType,
    status: String(raw.status ?? "draft") as MlModelSummary["status"],
    currentVersion: Number(raw.current_version ?? raw.currentVersion ?? 0),
    deployedVersion: (raw.deployed_version ?? raw.deployedVersion) as number | null | undefined,
    datasetId: (raw.dataset_id ?? raw.datasetId) as string | null | undefined,
    baseModel: (raw.base_model ?? raw.baseModel) as string | null | undefined,
    createdAt: (raw.created_at ?? raw.createdAt) as string | undefined,
    updatedAt: (raw.updated_at ?? raw.updatedAt) as string | undefined,
  }
}

// ============ ML model registry ============
export const mlModelsApi = {
  list: (params?: { modelType?: MlModelType; status?: string }) => {
    const query = new URLSearchParams()
    if (params?.modelType) query.set("model_type", params.modelType)
    if (params?.status) query.set("status", params.status)
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<MlModelListResponse>(apiUrl(`/api/ml/models${suffix}`)).then((res) => ({
      models: (res.models ?? []).map((m) =>
        normalizeMlModel(m as unknown as Record<string, unknown>)
      ),
    }))
  },
  get: async (id: string): Promise<MlModelDetail> => {
    const raw = await fetcher<Record<string, unknown>>(apiUrl(`/api/ml/models/${id}`))
    const versions = Array.isArray(raw.versions)
      ? raw.versions.map((v) => {
          const row = v as Record<string, unknown>
          return {
            version: Number(row.version ?? 0),
            metrics: (row.metrics as Record<string, unknown> | undefined) ?? undefined,
            artifactSizeBytes: (row.artifact_size_bytes ?? row.artifactSizeBytes) as number | null | undefined,
            createdAt: (row.created_at ?? row.createdAt) as string | undefined,
          }
        })
      : []
    return {
      ...normalizeMlModel(raw),
      taskType: (raw.task_type ?? raw.taskType) as string | null | undefined,
      versions,
    }
  },
  create: (data: CreateMlModelRequest) =>
    postJson<{ id: string; name: string; model_type: string; status: string }>(
      apiUrl("/api/ml/models"),
      data
    ),
  deploy: (id: string, version?: number) =>
    postJson<{ ok: boolean; deployed_version?: number | null }>(apiUrl(`/api/ml/models/${id}/deploy`), {
      version: version ?? null,
    }),
  predict: async (id: string, data: MlPredictRequest): Promise<MlPredictResponse> => {
    const raw = await postJson<Record<string, unknown>>(apiUrl(`/api/ml/models/${id}/predict`), {
      inputs: data.inputs,
      version: data.version ?? null,
      return_probabilities: data.return_probabilities ?? false,
    })
    return {
      modelId: String(raw.model_id ?? raw.modelId ?? id),
      version: Number(raw.version ?? 0),
      predictions: (raw.predictions as unknown[]) ?? [],
      probabilities: (raw.probabilities as Record<string, number>[] | null | undefined) ?? null,
      latencyMs: Number(raw.latency_ms ?? raw.latencyMs ?? 0),
    }
  },
}

// ============ Audit ============
export const auditApi = {
  list: (filters?: {
    user_id?: string
    entity_type?: string
    action?: string
    from?: string
    to?: string
    limit?: number
    offset?: number
  }) => {
    const params = new URLSearchParams()
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined) params.set(key, String(value))
      })
    }
    const query = params.toString()
    return fetcher<AuditListResponse>(apiUrl(`/api/audit${query ? `?${query}` : ""}`))
  },
  get: (id: string) => fetcher<AuditLog>(apiUrl(`/api/audit/${id}`)),
  summary: (range?: string) =>
    fetcher<AuditSummary>(apiUrl(`/api/audit/summary${range ? `?range=${range}` : ""}`)),
  export: async (format: "csv" | "json", from?: string, to?: string) => {
    const params = new URLSearchParams({ format })
    if (from) params.set("from", from)
    if (to) params.set("to", to)
    return apiFetch(apiUrl(`/api/audit/export?${params.toString()}`))
  },
}

// ============ Billing ============
export const billingApi = {
  overview: () => fetcher<BillingOverview>(apiUrl("/api/billing")),
  status: () =>
    fetcher<{
      billingStatus: string
      planCode?: string
      canAccessApp?: boolean
      requiresUpgrade?: boolean
      upgradeReason?: string | null
      trialEndsAt?: string | null
      currentPeriodEnd?: string | null
      cancelAtPeriodEnd?: boolean
    }>(apiUrl("/api/billing/status")),
  createCheckoutSession: (priceId: string, quantity?: number) =>
    postJson<{ checkout_url: string }>(apiUrl("/api/billing/checkout"), {
      price_id: priceId,
      quantity,
    }),
  createCheckoutForPlan: (planCode: string, billingInterval: "monthly" | "annual" = "monthly") =>
    postJson<{ checkout_url: string }>(apiUrl("/api/billing/checkout"), {
      plan_code: planCode,
      billing_interval: billingInterval,
    }),
  createSubscriptionForPlan: (planCode: string, billingInterval: "monthly" | "annual" = "monthly") =>
    postJson<{
      client_secret: string
      subscription_id: string
      customer_id: string
      subscription_status?: string
    }>(apiUrl("/api/billing/subscribe"), {
      plan_code: planCode,
      billing_interval: billingInterval,
    }),
  createPublicCheckoutForPlan: (
    planCode: string,
    billingInterval: "monthly" | "annual" = "monthly",
    email: string,
    companyName?: string,
  ) =>
    postJson<{ checkout_url: string }>(apiUrl("/api/billing/checkout/public"), {
      plan_code: planCode,
      billing_interval: billingInterval,
      email,
      company_name: companyName,
    }),
  createPortalSession: () =>
    postJson<{ portal_url: string }>(apiUrl("/api/billing/portal"), {}),
  updateSeats: (quantity: number) =>
    postJson<{ subscription: Subscription; prorated_amount?: number }>(
      apiUrl("/api/billing/seats"),
      { quantity }
    ),
  cancelSubscription: (atPeriodEnd?: boolean) =>
    postJson<Subscription>(apiUrl("/api/billing/cancel"), { at_period_end: atPeriodEnd ?? true }),
  reactivateSubscription: () =>
    postJson<Subscription>(apiUrl("/api/billing/reactivate"), {}),
  listInvoices: () => fetcher<{ invoices: Invoice[] }>(apiUrl("/api/billing/invoices")),
  downloadInvoice: (invoiceId: string) =>
    apiFetch(apiUrl(`/api/billing/invoices/${invoiceId}/pdf`)),
}

// ============ Metrics ============
export const metricsApi = {
  overview: (range?: string) =>
    fetcher<MetricsOverview>(apiUrl(`/api/metrics/overview${range ? `?range=${range}` : ""}`)),
  runs: (range?: string) =>
    fetcher<{ runVolume: Record<string, unknown>[]; latencyDistribution: Record<string, unknown>[] }>(
      apiUrl(`/api/metrics/runs${range ? `?range=${range}` : ""}`)
    ),
  insights: (range?: string) =>
    fetcher<{ insights: MetricInsight[] }>(apiUrl(`/api/metrics/insights${range ? `?range=${range}` : ""}`)),
  weeklyThroughput: () =>
    fetcher<{ weekStart: string; target: number; days: { day: string; records: number; target: number }[] }>(
      apiUrl("/api/metrics/weekly-throughput")
    ),
  exportCsv: (range?: string) =>
    apiFetch(apiUrl(`/api/metrics/export?format=csv${range ? `&range=${range}` : ""}`)),
  workflowStats: (workflowId: string) =>
    fetcher<{ runs: number; success_rate: number; avg_duration_ms: number }>(
      apiUrl(`/api/metrics/workflows/${workflowId}`)
    ),
}

// ============ Intelligence admin (v2 observability + v3 knowledge) ============
export type IntelligenceSnapshot = {
  queryVolume: {
    totalLogged: number
    distinctNormalized: number
    failedSearchCount: number
  }
  recentFailedSearches: Array<Record<string, unknown>>
  clusters: Array<Record<string, unknown>>
  glossary: Array<Record<string, unknown>>
  knowledgeGaps: Array<Record<string, unknown>>
  entityRelationships: Array<Record<string, unknown>>
}

export type IntelligenceLearningProgress = {
  queryRows: number
  queryRowsNeeded: number
  workflowRows: number
  workflowRowsNeeded: number
  clusteringRowsNeeded: number
  hasAnySnapshot: boolean
}

export type ResponseEvaluationRecord = {
  id: string
  messageId: string
  surface: string
  ragQualityScore: number | null
  userFeedback: "helpful" | "not_helpful" | null
  feedbackReason: string | null
  chunkOutcomeSummary: {
    chunksUsed: number
    avgReliability: number | null
    flaggedStaleSources: string[]
    retrievalLatencyMs: number | null
  } | null
  retrievalLatencyMs: number | null
  responseLatencyMs: number | null
  compositeScore: number | null
  evaluatedAt: string
}

export type IntelligenceEvaluationsResponse = {
  summary: {
    totalEvaluations: number
    pageCount: number
    helpfulCount: number
    notHelpfulCount: number
    avgCompositeScore: number | null
    avgRagQualityScore: number | null
    avgRetrievalLatencyMs: number | null
    avgResponseLatencyMs: number | null
  }
  compositeScoreWeights: {
    ragQualityScore: number
    userFeedback: number
    chunkReliabilityAvg: number
  }
  retrievalRanker: {
    trainingExamples: number
    minTrainingExamples: number
    isTrained: boolean
    isDeployed: boolean
    activeReliabilityWeight: number
    fallbackReliabilityWeight: number
    minLearnedWeight: number
    maxLearnedWeight: number
    usingLearnedWeight: boolean
    lastTrainedAt: string | null
    modelName: string
  }
  evaluations: ResponseEvaluationRecord[]
  pagination: {
    limit: number
    offset: number
    hasMore: boolean
  }
}

export const intelligencePacksApi = {
  packKpis: (packId: string) =>
    fetcher<{
      packId: string
      installed: boolean
      installId?: string | null
      agentCount?: number
      workflowCount?: number
      signalsCount?: number
      entitiesCount?: number
      cacheTouches?: number
      assignmentsCount?: number
      vendors?: Record<string, { signals?: number; entities?: number }>
    }>(apiUrl(`/api/intelligence-packs/${encodeURIComponent(packId)}/kpis`)),
}

export const intelligenceApi = {
  snapshot: () => fetcher<IntelligenceSnapshot>(apiUrl("/api/admin/intelligence/snapshot")),
  heuristicRecommendations: () =>
    fetcher<{
      advisoryOnly: boolean
      actionsTaken: unknown[]
      recommendations: Array<{
        id: string
        kind: string
        title: string
        reason: string
        confidence: number
        priority: number
        advisoryOnly: boolean
        href: string
      }>
      count: number
    }>(apiUrl("/api/intelligence/recommendations/heuristics")),
  dismissHeuristicRecommendation: (cardId: string) =>
    postJson<{ dismissed: boolean; cardId: string; advisoryOnly: boolean }>(
      apiUrl(`/api/intelligence/recommendations/heuristics/${encodeURIComponent(cardId)}/dismiss`),
      {},
    ),
  modelCatalog: () => fetcher<MlAdminCatalogResponse>(apiUrl("/api/intelligence/models/catalog")),
  learningProgress: () =>
    fetcher<IntelligenceLearningProgress>(apiUrl("/api/admin/intelligence/learning-progress")),
  evaluations: (params?: { limit?: number; offset?: number; sinceDays?: number }) => {
    const query = new URLSearchParams()
    if (params?.limit != null) query.set("limit", String(params.limit))
    if (params?.offset != null) query.set("offset", String(params.offset))
    if (params?.sinceDays != null) query.set("sinceDays", String(params.sinceDays))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<IntelligenceEvaluationsResponse>(apiUrl(`/api/admin/intelligence/evaluations${suffix}`))
  },
  relationships: (params?: { entityType?: string; entityId?: string }) => {
    const query = new URLSearchParams()
    if (params?.entityType) query.set("entityType", params.entityType)
    if (params?.entityId) query.set("entityId", params.entityId)
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<Record<string, unknown>>(apiUrl(`/api/admin/intelligence/relationships${suffix}`))
  },
  outcomes: (params?: { periodDays?: number }) => {
    const query = new URLSearchParams()
    if (params?.periodDays != null) query.set("periodDays", String(params.periodDays))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<IntelligenceOutcomesResponse & Record<string, unknown>>(
      apiUrl(`/api/admin/intelligence/outcomes${suffix}`),
    )
  },
  intelligenceEvaluations: (params?: { periodDays?: number }) => {
    const query = new URLSearchParams()
    if (params?.periodDays != null) query.set("periodDays", String(params.periodDays))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<Record<string, unknown>>(apiUrl(`/api/admin/intelligence/evaluations/intelligence${suffix}`))
  },
  trainingReadiness: () =>
    fetcher<Record<string, unknown>>(apiUrl("/api/intelligence/training-readiness")),
  banditStatus: () =>
    fetcher<Record<string, unknown>>(apiUrl("/api/admin/intelligence/learning/bandit-status")),
  memoryConflicts: () =>
    fetcher<Record<string, unknown>>(apiUrl("/api/admin/intelligence/learning/memory-conflicts")),
  learningLiveDashboard: () =>
    fetcher<Record<string, unknown>>(apiUrl("/api/admin/intelligence/learning/live-dashboard")),
  predictiveOpsDomain: (domain: string) =>
    fetcher<Record<string, unknown>>(
      apiUrl(`/api/admin/intelligence/predictive-ops/domain/${encodeURIComponent(domain)}`),
    ),
  routing: () => fetcher<Record<string, unknown>>(apiUrl("/api/admin/intelligence/routing")),
  simulations: () => fetcher<Record<string, unknown>>(apiUrl("/api/admin/intelligence/simulations")),
  trustSummary: (params?: { periodDays?: number }) => {
    const query = new URLSearchParams()
    if (params?.periodDays != null) query.set("periodDays", String(params.periodDays))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<Record<string, unknown>>(apiUrl(`/api/admin/intelligence/trust-summary${suffix}`))
  },
  businessImpact: () =>
    fetcher<{
      scopeNote: string
      businessImpactScore: number
      scoreLabel: string
      pendingReviewCount: number
      pendingBusinessSignals: number
      poorOutcomeAgents: number
      avgOutcomeWinRate: number | null
      revenueRiskItems: Array<{
        id: string
        severity: string
        title: string
        summary: string
        explanation?: string
        source: string
        suggestionType: string
        status?: string
        createdAt?: string | null
      }>
      dimensions: {
        revenueRisk: number
        outcomeHealth: number
        operationalLoad: number
      }
    }>(apiUrl("/api/admin/intelligence/business-impact")),
  connectorWrites: (params?: { periodDays?: number }) => {
    const query = new URLSearchParams()
    if (params?.periodDays != null) query.set("periodDays", String(params.periodDays))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<{
      orgId?: string
      periodDays: number
      since?: string
      spikeThreshold?: { failedRate: number; minN: number }
      totalEvents?: number
      rowCount?: number
      spikeCount?: number
      hasSpike?: boolean
      spikes?: Array<{
        vendor: string
        action: string
        n: number
        failed: number
        failedRate: number
        topErrorCodes?: Array<{ code: string; count: number }>
      }>
      rows?: Array<{
        vendor: string
        action: string
        requested: number
        completed: number
        failed: number
        n: number
        successRate: number
        failedRate: number
        topErrorCodes?: Array<{ code: string; count: number }>
        spike?: boolean
      }>
    }>(apiUrl(`/api/admin/intelligence/connector-writes${suffix}`))
  },
  engineSettings: () =>
    fetcher<{
      validationEnabled: boolean
      rerankingEnabled: boolean
      confidenceThreshold: number
      maxChunks: number
      connectorTimeoutSeconds: number
      performanceMode: string
    }>(apiUrl("/api/admin/intelligence/engine-settings")),
  updateEngineSettings: (data: {
    validation_enabled?: boolean
    reranking_enabled?: boolean
    confidence_threshold?: number
    max_chunks?: number
    connector_timeout_seconds?: number
    performance_mode?: string
  }) =>
    patchJson<{
      validationEnabled: boolean
      rerankingEnabled: boolean
      confidenceThreshold: number
      maxChunks: number
      connectorTimeoutSeconds: number
      performanceMode: string
    }>(apiUrl("/api/admin/intelligence/engine-settings"), data),
  performanceMode: () =>
    fetcher<{ mode: string }>(apiUrl("/api/admin/intelligence/performance-mode")),
  updatePerformanceMode: (data: { mode: string }) =>
    patchJson<{ mode: string }>(apiUrl("/api/admin/intelligence/performance-mode"), data),
  performance: (params?: { period?: "1h" | "24h" | "7d" }) => {
    const query = new URLSearchParams()
    if (params?.period) query.set("period", params.period)
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<{
      period: string
      avgTotalResponseMs: number
      p50TotalResponseMs: number
      p95TotalResponseMs: number
      byStage: Record<string, { avgMs: number; p50Ms: number; p95Ms: number; count: number }>
      cacheHitRate: Record<string, number>
      timeoutRate: number
      avgCostPerAnswerUsd: number
      byTier: Record<string, { count: number; avgMs: number; avgCost: number }>
      sampleCount: number
    }>(apiUrl(`/api/admin/intelligence/performance${suffix}`))
  },
  visibilityExplainability: () =>
    fetcher<Record<string, unknown>>(apiUrl("/api/intelligence/visibility/explainability")),
  visibilityTrustHealth: () =>
    fetcher<import("@/lib/intelligence/visibility-types").VisibilityTrustHealth>(
      apiUrl("/api/intelligence/visibility/trust-health"),
    ),
  visibilityMaturity: () =>
    fetcher<{ status?: string; org_id?: string; maturity?: import("@/lib/intelligence/visibility-types").IntelligenceMaturityView }>(
      apiUrl("/api/intelligence/visibility/maturity"),
    ),
  visibilityLearningHealth: () =>
    fetcher<Record<string, unknown>>(apiUrl("/api/intelligence/visibility/learning-health")),
  visibilityDomainHealth: () =>
    fetcher<import("@/lib/intelligence/visibility-types").VisibilityDomainHealth>(
      apiUrl("/api/intelligence/visibility/domain-health"),
    ),
  visibilityKnowledgeHealth: () =>
    fetcher<Record<string, unknown>>(apiUrl("/api/intelligence/visibility/knowledge-health")),
  visibilityExecutive: () =>
    fetcher<import("@/lib/intelligence/visibility-types").ExecutiveIntelligenceSummary>(
      apiUrl("/api/intelligence/visibility/executive"),
    ),
  visibilityAgent: (agentId: string) =>
    fetcher<import("@/lib/intelligence/visibility-types").AgentVisibilityProfile>(
      apiUrl(`/api/intelligence/visibility/agents/${encodeURIComponent(agentId)}`),
    ),
}

export const architectureAdminApi = {
  aiOsStatus: () => fetcher<Record<string, unknown>>(apiUrl("/api/admin/ai-os/status")),
  predictiveOps: () => fetcher<Record<string, unknown>>(apiUrl("/api/admin/intelligence/predictive-ops")),
  learningStatus: () => fetcher<Record<string, unknown>>(apiUrl("/api/admin/learning/status")),
  optimizationSummary: () => fetcher<Record<string, unknown>>(apiUrl("/api/admin/optimization/summary")),
}

export type ChatAdminPersona = {
  persona_key: string
  label: string
  tone?: string | null
  verbosity?: string | null
  formality?: string | null
  is_org_default?: boolean
}

export const chatAdminApi = {
  personas: () =>
    fetcher<{ personas: ChatAdminPersona[]; org_default_persona: string }>(
      apiUrl("/api/admin/chat/personas"),
    ),
  setDefaultPersona: (persona_key: string) =>
    postJson<{ status: string; default_persona?: string; message?: string }>(
      apiUrl("/api/admin/chat/personas/default"),
      { persona_key },
    ),
}

export type MlAdminOrgModelStatus = {
  model_name: string
  catalog_status: string
  advisory_only?: boolean
  use_cases?: string[]
  activation?: string
  fallback?: string
  data_counts?: Record<string, number>
}

export type MlAdminCatalogResponse = {
  catalog: Record<string, Record<string, unknown>>
  orgTrainingStatus: Record<string, MlAdminOrgModelStatus>
  outcomeScores?: Record<string, number | null>
}

export type MlAdminTrainResult = {
  model_name?: string
  org_id?: string
  trained?: boolean
  temporal?: boolean
  workflow_id?: string
  reason?: string
  required?: number
  query_rows?: number
  distinct_queries?: number
  resolved_candidates?: number
  training_examples?: number
  model_id?: string | null
  latency_ms?: number
  message?: string
}

export const mlAdminApi = {
  listCatalog: () => fetcher<MlAdminCatalogResponse>(apiUrl("/api/admin/ml/models")),
  modelStatus: (modelName: string) =>
    fetcher<MlAdminOrgModelStatus>(apiUrl(`/api/admin/ml/models/${modelName}/status`)),
  trainModel: (modelName: string) =>
    postJson<MlAdminTrainResult>(apiUrl(`/api/admin/ml/models/${modelName}/train`), {}),
}

export type IntelligenceOutcomesAgentSummary = {
  agentId: string
  agentName?: string
  sampleSize: number
  minSampleSize: number
  sufficientData: boolean
  confidenceNote: string
  message?: string
  winRate?: number | null
  avgMetricDelta?: number | null
}

export type IntelligenceOutcomesResponse = {
  scopeNote: string
  confidenceNote: string
  minSampleSize: number
  pendingMeasurements: number
  observableMetrics: Array<{ connector: string; entityType: string; metric: string }>
  agentSummaries: IntelligenceOutcomesAgentSummary[]
}

// ============ Memory Promotion (v4) ============
export type PromotionThresholdComparison = {
  frequency: number | null
  departmentCount: number | null
  autoPromoteMinOccurrences: number
  autoPromoteMinDepartments: number
  meetsAutoThreshold: boolean
  canAutoPromote: boolean
}

export type PromotionCandidate = {
  id: string
  candidate_type?: string | null
  content?: string | null
  memory_category?: string | null
  status?: string | null
  source_table?: string | null
  frequency?: number | null
  department_count?: number | null
  metadata?: Record<string, unknown> | null
  updated_at?: string | null
  thresholdComparison?: PromotionThresholdComparison
  [key: string]: unknown
}

export type PromotionCandidatesResponse = {
  items: PromotionCandidate[]
  total: number
  limit: number
  offset: number
}

export type AutoPromotionRecord = {
  memory_id?: string | null
  candidate_id?: string | null
  source_table?: string | null
  action?: string | null
  decided_at?: string | null
  decided_by?: string | null
  promotionPath?: string | null
  decisionReasoning?: string | null
  rollbackPath?: string | null
  [key: string]: unknown
}

export type RecentAutoPromotionsResponse = {
  items: AutoPromotionRecord[]
  since: string
  rollbackEndpoint: string
}

export const memoryPromotionApi = {
  candidates: (params?: { status?: string; source?: string; limit?: number; offset?: number }) => {
    const query = new URLSearchParams()
    if (params?.status) query.set("status", params.status)
    if (params?.source) query.set("source", params.source)
    if (params?.limit != null) query.set("limit", String(params.limit))
    if (params?.offset != null) query.set("offset", String(params.offset))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<PromotionCandidatesResponse>(apiUrl(`/api/admin/memory-promotion/candidates${suffix}`))
  },
  approve: (candidateId: string) =>
    postJson<Record<string, unknown>>(
      apiUrl(`/api/admin/memory-promotion/candidates/${candidateId}/approve`),
      {},
    ),
  reject: (candidateId: string, reason?: string) =>
    postJson<{ status: string }>(
      apiUrl(`/api/admin/memory-promotion/candidates/${candidateId}/reject`),
      { reason: reason ?? null },
    ),
  recentAutoPromotions: (params?: { since?: string; limit?: number }) => {
    const query = new URLSearchParams()
    if (params?.since) query.set("since", params.since)
    if (params?.limit != null) query.set("limit", String(params.limit))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<RecentAutoPromotionsResponse>(
      apiUrl(`/api/admin/memory-promotion/recent-auto-promotions${suffix}`),
    )
  },
  audit: (params?: { memoryId?: string; since?: string; limit?: number; offset?: number }) => {
    const query = new URLSearchParams()
    if (params?.memoryId) query.set("memory_id", params.memoryId)
    if (params?.since) query.set("since", params.since)
    if (params?.limit != null) query.set("limit", String(params.limit))
    if (params?.offset != null) query.set("offset", String(params.offset))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<Record<string, unknown>>(apiUrl(`/api/admin/memory-promotion/audit${suffix}`))
  },
  rollback: (memoryId: string, reason: string) =>
    postJson<{ status: string }>(
      apiUrl(`/api/admin/memory-promotion/memories/${memoryId}/rollback`),
      { reason },
    ),
}

// ============ Settings ============
export const settingsApi = {
  get: () => fetcher<Record<string, unknown>>(apiUrl("/api/settings")),
  update: (data: Record<string, unknown>) => patchJson<Record<string, unknown>>(apiUrl("/api/settings"), data),
  
  // Organization
  getOrg: () => fetcher<{ organization: Record<string, unknown> }>(apiUrl("/api/settings/organization")),
  updateOrg: (data: Record<string, unknown>) =>
    patchJson<{ organization: Record<string, unknown> }>(apiUrl("/api/settings/organization"), data),
  
  // Team
  listTeamMembers: () => fetcher<{ team: User[] }>(apiUrl("/api/settings/team")),
  inviteMember: (email: string, role?: string) =>
    postJson<{ member: User }>(apiUrl("/api/settings/team"), { email, role }),
  removeMember: async (userId: string) => {
    const response = await apiFetch(apiUrl("/api/settings/team"), {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: userId }),
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `Request failed: ${response.status}`)
    }
  },

  // API Keys
  listApiKeys: () => fetcher<ApiKeyListResponse>(apiUrl("/api/settings/api-keys")),
  createApiKey: (name: string) => postJson<{ apiKey: ApiKey }>(apiUrl("/api/settings/api-keys"), { name }),
  rotateApiKey: (id: string) =>
    postJson<{ apiKey: ApiKey }>(apiUrl(`/api/settings/api-keys/${id}/rotate`), {}),
  revokeApiKey: (id: string) =>
    patchJson<{ apiKey: ApiKey }>(apiUrl("/api/settings/api-keys"), { id, status: "revoked" }),

  // Lite seats / departments
  getLiteSeats: () => fetcher<LiteSeatsResponse>(apiUrl("/api/settings/lite-seats")),
  createDepartment: (data: { name: string; lite_seat_allocation: number; department_admin_id?: string }) =>
    postJson<{ department: Record<string, unknown> }>(apiUrl("/api/settings/lite-seats"), data),
  updateDepartment: (data: {
    id: string
    name?: string
    lite_seat_allocation?: number
    department_admin_id?: string
  }) => patchJson<{ department: Record<string, unknown> }>(apiUrl("/api/settings/lite-seats"), data),
  deleteDepartment: async (departmentId: string) => {
    const response = await apiFetch(apiUrl(`/api/settings/lite-seats?departmentId=${encodeURIComponent(departmentId)}`), {
      method: "DELETE",
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `Request failed: ${response.status}`)
    }
  },
  addDepartmentMember: (data: { department_id: string; user_email: string; role?: string }) =>
    postJson<{ member: Record<string, unknown> }>(apiUrl("/api/settings/lite-seats/members"), data),
  removeDepartmentMember: async (departmentId: string, userId: string) => {
    const response = await apiFetch(
      apiUrl(
        `/api/settings/lite-seats/members?departmentId=${encodeURIComponent(departmentId)}&userId=${encodeURIComponent(userId)}`,
      ),
      { method: "DELETE" },
    )
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `Request failed: ${response.status}`)
    }
  },
  getLiteMembership: () =>
    fetcher<{ is_lite: boolean; is_admin: boolean; department: { id: string; name: string } | null }>(
      apiUrl("/api/settings/lite-membership"),
    ),

  // Meson addons
  getMesonAddons: () => fetcher<MesonAddonsResponse>(apiUrl("/api/settings/meson-addons")),
  toggleMesonAddon: (code: string, enabled: boolean) =>
    patchJson<{ subscription: Record<string, unknown> }>(apiUrl("/api/settings/meson-addons"), { code, enabled }),

  // Usage-based billing
  getBillingUsage: () => fetcher<BillingUsageResponse>(apiUrl("/api/settings/billing-usage")),

  // STA-316 Memory Option B — opaque-token entity embeddings (opt-in)
  getMemoryEntityEmbeddings: () =>
    fetcher<{ memoryEntityEmbeddings: { enabled: boolean; connectors: string[] } }>(
      apiUrl("/api/settings/memory-entity-embeddings"),
    ),
  updateMemoryEntityEmbeddings: (data: { enabled: boolean; connectors: string[] }) =>
    putJson<{ memoryEntityEmbeddings: { enabled: boolean; connectors: string[] } }>(
      apiUrl("/api/settings/memory-entity-embeddings"),
      data,
    ),
}

// ============ Environments ============
export const environmentsApi = {
  list: () =>
    fetcher<{ environments: { id: string; name: string; is_default: boolean }[] }>(apiUrl("/api/environments")),
  create: (data: { name: string }) =>
    postJson<{ id: string; name: string }>(apiUrl("/api/environments"), data),
  delete: (id: string) => deleteRequest(apiUrl(`/api/environments/${id}`)),
}

// ============ Organizations ============
export const organizationsApi = {
  list: () => fetcher<{ organizations: Organization[] }>(apiUrl("/api/organizations")),
  get: (id: string) => fetcher<Organization>(apiUrl(`/api/organizations/${id}`)),
  create: (data: { name: string; slug?: string }) =>
    postJson<Organization>(apiUrl("/api/organizations"), data),
  update: (id: string, data: Partial<Organization>) =>
    patchJson<Organization>(apiUrl(`/api/organizations/${id}`), data),
  delete: (id: string) => deleteRequest(apiUrl(`/api/organizations/${id}`)),
  switch: (id: string) => postJson<{ token: string }>(apiUrl(`/api/organizations/${id}/switch`), {}),
  listMembers: (orgId: string) =>
    fetcher<{ members: (User & { role: string })[] }>(apiUrl(`/api/organizations/${orgId}/members`)),
  inviteMember: (orgId: string, email: string, role?: string) =>
    postJson<void>(apiUrl(`/api/organizations/${orgId}/members/invite`), { email, role }),
  updateMemberRole: (orgId: string, userId: string, role: string) =>
    patchJson<void>(apiUrl(`/api/organizations/${orgId}/members/${userId}`), { role }),
  removeMember: (orgId: string, userId: string) =>
    deleteRequest(apiUrl(`/api/organizations/${orgId}/members/${userId}`)),
  transferOwnership: (orgId: string, newOwnerId: string) =>
    postJson<void>(apiUrl(`/api/organizations/${orgId}/transfer`), { new_owner_id: newOwnerId }),
}

export type OrgRolePermissionsMatrix = {
  roles: string[]
  capabilities: Array<{
    key: string
    capability: string
    access: Record<string, boolean>
  }>
}

export const orgApi = {
  getRolePermissions: () => fetcher<OrgRolePermissionsMatrix>(apiUrl("/api/org/role-permissions")),
}

// ============ Notifications ============
export const notificationsApi = {
  list: (filters?: { unread_only?: boolean; limit?: number; offset?: number }) => {
    const params = new URLSearchParams()
    if (filters?.unread_only) params.set("unread_only", "true")
    if (filters?.limit) params.set("limit", String(filters.limit))
    if (filters?.offset) params.set("offset", String(filters.offset))
    const query = params.toString()
    return fetcher<NotificationListResponse>(apiUrl(`/api/notifications${query ? `?${query}` : ""}`))
  },
  getUnreadCount: () =>
    fetcher<{ count: number }>(apiUrl("/api/notifications/unread-count")),
  markRead: (id: string) =>
    postJson<void>(apiUrl(`/api/notifications/${id}/read`), {}),
  markAllRead: () =>
    postJson<void>(apiUrl("/api/notifications/read-all"), {}),
  archive: (id: string) =>
    postJson<void>(apiUrl(`/api/notifications/${id}/archive`), {}),
  delete: (id: string) =>
    deleteRequest(apiUrl(`/api/notifications/${id}`)),
  getPreferences: () =>
    fetcher<{ preferences: Record<string, { bell_enabled: boolean; email_enabled: boolean }> }>(
      apiUrl("/api/notifications/preferences"),
    ),
  updatePreferences: (preferences: Record<string, { bell_enabled: boolean; email_enabled: boolean }>) =>
    patchJson<void>(apiUrl("/api/notifications/preferences"), preferences),
  streamUrl: () => apiUrl("/api/notifications/stream"),
}

// ============ Onboarding ============
export const onboardingApi = {
  getProgress: () =>
    fetcher<OnboardingProgress>(apiUrl("/api/onboarding")),
  bootstrap: () =>
    postJson<{
      org_id: string
      seeded: boolean
      agents_created: number
      workflows_created: number
      runs_created: number
      welcome_message: string
    }>(apiUrl("/api/onboarding/bootstrap"), {}),
  completeStep: (stepKey: string, data?: Record<string, unknown>) =>
    postJson<OnboardingProgress>(apiUrl("/api/onboarding/complete-step"), {
      step_key: stepKey,
      data,
    }),
  skip: () =>
    postJson<void>(apiUrl("/api/onboarding/skip"), {}),
  welcomeComplete: (role: string, skippedOptional = false) =>
    postJson<OnboardingProgress>(apiUrl("/api/onboarding/welcome-complete"), {
      role,
      skipped_optional: skippedOptional,
    }),
  reset: () =>
    postJson<OnboardingProgress>(apiUrl("/api/onboarding/reset"), {}),
}

// ============ Lite Mode ============
export const liteApi = {
  // Home
  home: () => fetcher<LiteHomeData>(apiUrl("/api/lite/home")),

  // Assign Work
  getAvailableWorkflows: () =>
    fetcher<{ workflows: { id: string; name: string; description?: string; required_inputs: string[] }[] }>(
      apiUrl("/api/lite/workflows")
    ),
  assignWork: (workflowId: string, inputs: Record<string, unknown>, notes?: string) =>
    postJson<{ task_id: string }>(apiUrl("/api/lite/assign"), {
      workflow_id: workflowId,
      inputs,
      notes,
    }),

  // Tasks
  listTasks: (filters?: { status?: string }) => {
    const params = new URLSearchParams()
    if (filters?.status) params.set("status", filters.status)
    const query = params.toString()
    return fetcher<{ tasks: LiteTask[] }>(apiUrl(`/api/lite/tasks${query ? `?${query}` : ""}`))
  },
  getTask: (id: string) => fetcher<LiteTask>(apiUrl(`/api/lite/tasks/${id}`)),
  cancelTask: (id: string) => postJson<void>(apiUrl(`/api/lite/tasks/${id}/cancel`), {}),

  // Deliverables
  listDeliverables: () =>
    fetcher<{ deliverables: LiteDeliverable[] }>(apiUrl("/api/lite/deliverables")),
  downloadDeliverable: (id: string) =>
    apiFetch(apiUrl(`/api/lite/deliverables/${id}/download`)),

  // Results
  getResults: (range?: string) => {
    const params = range ? `?range=${range}` : ""
    return fetcher<{ summary: LiteResultsSummary; recent: LiteTask[] }>(
      apiUrl(`/api/lite/results${params}`)
    )
  },
}

// ============ SSO ============
export const ssoApi = {
  getConfig: () =>
    fetcher<SSOConfiguration | null>(apiUrl("/api/auth/sso/config")),
  saveConfig: (data: SSOConfigurationCreate) =>
    postJson<SSOConfiguration>(apiUrl("/api/auth/sso/config"), data),
  enable: () =>
    postJson<{ enabled: boolean }>(apiUrl("/api/auth/sso/config/enable"), {}),
  disable: () =>
    postJson<{ enabled: boolean }>(apiUrl("/api/auth/sso/config/disable"), {}),
  deleteConfig: () =>
    deleteRequest(apiUrl("/api/auth/sso/config")),
  initLogin: () =>
    postJson<SSOInitResponse>(apiUrl("/api/auth/sso/init"), {}),
}

// Convenience export for all APIs
// ============ Enterprise Admin ============
export const enterpriseApi = {
  // Data residency
  getDataRegion: () => fetcher<EnterpriseDataRegion>(apiUrl("/api/enterprise/data-region")),
  updateDataRegion: (data: { region: EnterpriseDataRegion["region"] }) =>
    putJson<EnterpriseDataRegion>(apiUrl("/api/enterprise/data-region"), data),

  // Branding
  getBranding: () => fetcher<EnterpriseBranding>(apiUrl("/api/enterprise/branding")),
  updateBranding: (data: Partial<EnterpriseBranding>) =>
    putJson<EnterpriseBranding>(apiUrl("/api/enterprise/branding"), data),
  getDomainInstructions: () =>
    fetcher<EnterpriseDomainInstructions>(apiUrl("/api/enterprise/branding/domain-instructions")),
  verifyDomain: () =>
    postJson<EnterpriseDomainVerifyResult>(apiUrl("/api/enterprise/branding/verify-domain"), {}),

  // Workforce analytics
  getWorkforceAnalytics: () =>
    fetcher<EnterpriseWorkforceAnalytics>(apiUrl("/api/enterprise/workforce-analytics")),

  // Cost attribution
  getCostAttribution: () =>
    fetcher<EnterpriseCostAttribution>(apiUrl("/api/enterprise/cost-attribution")),

  // Autonomous run budgets (STA-109)
  getAutonomousRunBudgets: () =>
    fetcher<EnterpriseAutonomousRunBudgets>(apiUrl("/api/enterprise/autonomous-run-budgets")),
  updateAutonomousRunBudgets: (data: Partial<AutonomousRunBudgetLimits> & { unset?: string[] }) =>
    putJson<EnterpriseAutonomousRunBudgets>(apiUrl("/api/enterprise/autonomous-run-budgets"), data),
  updateAgentRunBudgets: (
    agentId: string,
    data: Partial<AutonomousRunBudgetLimits> & { unset?: string[] },
  ) =>
    putJson<{
      agent: unknown
      limits: AutonomousRunBudgetLimits
      usageToday: AutonomousRunBudgetUsage
      usageDate: string
    }>(apiUrl(`/api/agents/${agentId}/run-budgets`), data),

  // HIPAA (STA-110)
  getHipaa: () => fetcher<EnterpriseHipaaStatus>(apiUrl("/api/enterprise/hipaa")),
  acceptHipaaBaa: (data?: { baaVersion?: string }) =>
    postJson<EnterpriseHipaaStatus>(apiUrl("/api/enterprise/hipaa/accept-baa"), data ?? {}),
  updateHipaa: (data: { enabled: boolean }) =>
    putJson<EnterpriseHipaaStatus>(apiUrl("/api/enterprise/hipaa"), data),

  // EU AI Act transparency (STA-112)
  getTransparencyLogs: (params?: { from?: string; to?: string; limit?: number }) => {
    const query = new URLSearchParams()
    if (params?.from) query.set("from", params.from)
    if (params?.to) query.set("to", params.to)
    if (params?.limit) query.set("limit", String(params.limit))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<EnterpriseTransparencyLogsResponse>(
      apiUrl(`/api/enterprise/transparency-logs${suffix}`),
    )
  },
  exportTransparencyLogs: (params?: { from?: string; to?: string }) => {
    const query = new URLSearchParams()
    if (params?.from) query.set("from", params.from)
    if (params?.to) query.set("to", params.to)
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<EnterpriseTransparencyExport>(
      apiUrl(`/api/enterprise/transparency-logs/export${suffix}`),
    )
  },

  // SIEM
  getSiem: () => fetcher<EnterpriseSiemConfig>(apiUrl("/api/enterprise/siem")),
  updateSiem: (data: { enabled?: boolean; endpoint?: string | null; secret?: string | null }) =>
    putJson<EnterpriseSiemConfig>(apiUrl("/api/enterprise/siem"), data),
  testSiem: () => postJson<EnterpriseSiemTestResult>(apiUrl("/api/enterprise/siem/test"), {}),

  // CS dashboard — integration health (STA-124)
  getIntegrationHealth: (lookbackDays = 30) =>
    fetcher<IntegrationHealthScore>(
      apiUrl(`/api/enterprise/integration-health?lookbackDays=${lookbackDays}`),
    ),
  recordIntegrationHealthSnapshot: (lookbackDays = 30) =>
    postJson<{ snapshot: IntegrationHealthSnapshot; health: IntegrationHealthScore }>(
      apiUrl(`/api/enterprise/integration-health/snapshot?lookbackDays=${lookbackDays}`),
      {},
    ),
  getIntegrationHealthHistory: (limit = 30) =>
    fetcher<IntegrationHealthHistoryResponse>(
      apiUrl(`/api/enterprise/integration-health/history?limit=${limit}`),
    ),

  // CS dashboard — integration suggestions (STA-123)
  getIntegrationSuggestions: (params?: { status?: string; connectorType?: string }) => {
    const query = new URLSearchParams()
    if (params?.status) query.set("status", params.status)
    if (params?.connectorType) query.set("connectorType", params.connectorType)
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<IntegrationSuggestionsResponse>(apiUrl(`/api/enterprise/integration-suggestions${suffix}`))
  },
  scanIntegrationSuggestions: (lookbackDays = 30) =>
    postJson<IntegrationSuggestionScanResponse>(
      apiUrl(`/api/enterprise/integration-suggestions/scan?lookbackDays=${lookbackDays}`),
      {},
    ),
  dismissIntegrationSuggestion: (suggestionId: string) =>
    postJson<{ suggestion: IntegrationSuggestion }>(
      apiUrl(`/api/enterprise/integration-suggestions/${suggestionId}/dismiss`),
      {},
    ),
  applyIntegrationSuggestion: (suggestionId: string) =>
    postJson<IntegrationSuggestionApplyResponse>(
      apiUrl(`/api/enterprise/integration-suggestions/${suggestionId}/apply`),
      {},
    ),
  confirmIntegrationSuggestion: (suggestionId: string) =>
    postJson<IntegrationSuggestionApplyResponse>(
      apiUrl(`/api/enterprise/integration-suggestions/${suggestionId}/confirm`),
      {},
    ),
}

// ============ Knowledge sync (STA-45, org-admin) ============
export const knowledgeSyncApi = {
  listSyncJobs: (params?: { connectorId?: string; limit?: number }) => {
    const query = new URLSearchParams()
    if (params?.connectorId) query.set("connectorId", params.connectorId)
    if (params?.limit) query.set("limit", String(params.limit))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<KnowledgeSyncJobsResponse>(apiUrl(`/api/knowledge/sync-jobs${suffix}`))
  },
  triggerConnectorSync: (connectorId: string, data?: { fullSync?: boolean }) =>
    postJson<KnowledgeSyncTriggerResponse>(
      apiUrl(`/api/knowledge/connectors/${connectorId}/sync`),
      { fullSync: data?.fullSync ?? false },
    ),
}

// ============ RAG admin ingest (STA-279) ============
export const ragAdminApi = {
  ingestFile: async (params: {
    sourceId: string
    file: File
    externalId?: string
    title?: string
    metadata?: Record<string, unknown>
  }) => {
    const form = new FormData()
    form.append("source_id", params.sourceId)
    form.append("file", params.file)
    if (params.externalId) form.append("external_id", params.externalId)
    if (params.title) form.append("title", params.title)
    if (params.metadata) form.append("metadata_json", JSON.stringify(params.metadata))
    const response = await apiFetch(apiUrl("/api/rag/ingest/file"), {
      method: "POST",
      body: form,
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}))
      throw new Error(
        typeof payload === "object" && payload && "detail" in payload
          ? String((payload as { detail?: string }).detail)
          : "File ingest failed",
      )
    }
    return response.json() as Promise<{
      ingest_id: string
      status: string
      filename: string
      extracted_chars: number
    }>
  },
  embeddingStatus: () =>
    fetcher<{
      primary_provider: string
      openai_configured: boolean
      voyage_enabled: boolean
      voyage_configured: boolean
      corpus_dimension: number
      voyage_dimension: number
      voyage_dimension_compatible: boolean
      reindex_required_for_voyage: boolean
    }>(apiUrl("/api/rag/embedding-status")),
}

export const platformApi = {
  getCsWorkspaceTenants: (params?: { limit?: number; grade?: string; hideSnoozed?: boolean }) => {
    const query = new URLSearchParams()
    if (params?.limit) query.set("limit", String(params.limit))
    if (params?.grade) query.set("grade", params.grade)
    if (params?.hideSnoozed) query.set("hideSnoozed", "true")
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<PlatformCsWorkspaceResponse>(apiUrl(`/api/platform/cs-workspace/tenants${suffix}`))
  },
  backfillHealthSnapshots: (params?: { limit?: number; lookbackDays?: number }) => {
    const query = new URLSearchParams()
    if (params?.limit) query.set("limit", String(params.limit))
    if (params?.lookbackDays) query.set("lookbackDays", String(params.lookbackDays))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return postJson<PlatformCsSnapshotBackfillResponse>(
      apiUrl(`/api/platform/cs-workspace/snapshots/backfill${suffix}`),
      {},
    )
  },
  assignTenant: (orgId: string, data?: { note?: string }) =>
    postJson<PlatformCsTenantQueueActionResponse>(
      apiUrl(`/api/platform/cs-workspace/tenants/${encodeURIComponent(orgId)}/assign`),
      data ?? {},
    ),
  snoozeTenant: (orgId: string, hours: number) =>
    postJson<PlatformCsTenantQueueActionResponse>(
      apiUrl(`/api/platform/cs-workspace/tenants/${encodeURIComponent(orgId)}/snooze`),
      { hours },
    ),
  getCsAlerts: (params?: { limit?: number; offset?: number; alertType?: "failure" | "suggestion" }) => {
    const query = new URLSearchParams()
    if (params?.limit) query.set("limit", String(params.limit))
    if (params?.offset) query.set("offset", String(params.offset))
    if (params?.alertType) query.set("alertType", params.alertType)
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<PlatformCsAlertsResponse>(apiUrl(`/api/platform/cs-workspace/alerts${suffix}`))
  },
  escalateTenant: (orgId: string, data?: { note?: string }) =>
    postJson<PlatformCsEscalateResponse>(
      apiUrl(`/api/platform/cs-workspace/tenants/${encodeURIComponent(orgId)}/escalate`),
      data ?? {},
    ),
}

export const federationApi = {
  // Partnerships — always use same-origin /api routes (Next rewrite → FastAPI)
  listPartnerships: () =>
    fetcher<{ partnerships: FederationPartnership[] }>("/api/federation/partnerships"),
  invitePartner: (partnerOrgId: string) =>
    postJson<{ partnership: FederationPartnership }>("/api/federation/partnerships", {
      partnerOrgId,
    }),
  acceptPartnership: (partnershipId: string) =>
    postJson<{ partnership: FederationPartnership }>(
      `/api/federation/partnerships/${partnershipId}/accept`,
      {},
    ),
  rejectPartnership: (partnershipId: string) =>
    postJson<{ partnership: FederationPartnership }>(
      `/api/federation/partnerships/${partnershipId}/reject`,
      {},
    ),
  revokePartnership: (partnershipId: string) =>
    postJson<{ partnership: FederationPartnership }>(
      `/api/federation/partnerships/${partnershipId}/revoke`,
      {},
    ),

  // Handoffs
  listHandoffs: (params?: { direction?: "all" | "inbound" | "outbound"; status?: string }) => {
    const query = new URLSearchParams()
    if (params?.direction) query.set("direction", params.direction)
    if (params?.status) query.set("status", params.status)
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<{ handoffs: FederationHandoff[] }>(`/api/federation/handoffs${suffix}`)
  },
  createHandoff: (data: CreateFederationHandoffRequest) =>
    postJson<{ handoff: FederationHandoff }>("/api/federation/handoffs", data),
  acceptHandoff: (handoffId: string) =>
    postJson<{ handoff: FederationHandoff }>(
      `/api/federation/handoffs/${handoffId}/accept`,
      {},
    ),
  rejectHandoff: (handoffId: string, reason?: string) =>
    postJson<{ handoff: FederationHandoff }>(
      `/api/federation/handoffs/${handoffId}/reject`,
      { reason },
    ),

  // Connector grants
  listConnectorGrants: () =>
    fetcher<{ grants: FederationConnectorGrant[] }>("/api/federation/connector-grants"),
  proposeConnectorGrant: (data: CreateFederationConnectorGrantRequest) =>
    postJson<{ grant: FederationConnectorGrant }>("/api/federation/connector-grants", data),
  acceptConnectorGrant: (grantId: string) =>
    postJson<{ grant: FederationConnectorGrant }>(
      `/api/federation/connector-grants/${grantId}/accept`,
      {},
    ),
  rejectConnectorGrant: (grantId: string) =>
    postJson<{ grant: FederationConnectorGrant }>(
      `/api/federation/connector-grants/${grantId}/reject`,
      {},
    ),
  revokeConnectorGrant: (grantId: string) =>
    postJson<{ grant: FederationConnectorGrant }>(
      `/api/federation/connector-grants/${grantId}/revoke`,
      {},
    ),

  // Delegated tasks
  listDelegatedTasks: (params?: { direction?: "all" | "inbound" | "outbound"; status?: string }) => {
    const query = new URLSearchParams()
    if (params?.direction) query.set("direction", params.direction)
    if (params?.status) query.set("status", params.status)
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<{ tasks: FederationDelegatedTask[] }>(`/api/federation/delegated-tasks${suffix}`)
  },
  createDelegatedTask: (data: CreateFederationDelegatedTaskRequest) =>
    postJson<{ task: FederationDelegatedTask }>("/api/federation/delegated-tasks", data),
  acceptDelegatedTask: (taskId: string) =>
    postJson<{ task: FederationDelegatedTask }>(`/api/federation/delegated-tasks/${taskId}/accept`, {}),
  rejectDelegatedTask: (taskId: string, reason?: string) =>
    postJson<{ task: FederationDelegatedTask }>(
      `/api/federation/delegated-tasks/${taskId}/reject`,
      { reason: reason ?? "Declined by operator" },
    ),
}

// ============ Agent swarm (STA-119) ============
export const agentSwarmApi = {
  list: (params?: { status?: string; limit?: number }) => {
    const query = new URLSearchParams()
    if (params?.status) query.set("status", params.status)
    if (params?.limit) query.set("limit", String(params.limit))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return fetcher<AgentSwarmListResponse>(apiUrl(`/api/agent-swarm${suffix}`))
  },
  get: (swarmRunId: string) => fetcher<AgentSwarmRun>(apiUrl(`/api/agent-swarm/${swarmRunId}`)),
  start: (data: AgentSwarmStartRequest) =>
    postJson<AgentSwarmRun>(apiUrl("/api/agent-swarm/start"), data),
  aggregate: (swarmRunId: string) =>
    postJson<AgentSwarmRun>(apiUrl(`/api/agent-swarm/${swarmRunId}/aggregate`), {}),
  cancel: (swarmRunId: string) =>
    postJson<AgentSwarmRun>(apiUrl(`/api/agent-swarm/${swarmRunId}/cancel`), {}),
}

// ============ Vertical industry packs (STA-113–115) ============
export const verticalsApi = {
  getHealthcare: () => fetcher<Record<string, unknown>>(apiUrl("/api/verticals/healthcare")),
  installHealthcare: () => postJson<Record<string, unknown>>(apiUrl("/api/verticals/healthcare/install"), {}),
  getLegal: () => fetcher<Record<string, unknown>>(apiUrl("/api/verticals/legal")),
  installLegal: () => postJson<Record<string, unknown>>(apiUrl("/api/verticals/legal/install"), {}),
  getRealEstate: () => fetcher<Record<string, unknown>>(apiUrl("/api/verticals/real-estate")),
  installRealEstate: () => postJson<Record<string, unknown>>(apiUrl("/api/verticals/real-estate/install"), {}),
}

export const api = {
  auth: authApi,
  operators: operatorsApi,
  agents: agentsApi,
  workflows: workflowsApi,
  schedules: schedulesApi,
  runs: runsApi,
  agentInterrupts: agentInterruptsApi,
  approvals: approvalsApi,
  connectors: connectorsApi,
  marketplace: marketplaceApi,
  sources: sourcesApi,
  search: searchApi,
  training: trainingApi,
  mlModels: mlModelsApi,
  audit: auditApi,
  billing: billingApi,
  metrics: metricsApi,
  intelligence: intelligenceApi,
  chatAdmin: chatAdminApi,
  mlAdmin: mlAdminApi,
  memoryPromotion: memoryPromotionApi,
  settings: settingsApi,
  environments: environmentsApi,
  organizations: organizationsApi,
  notifications: notificationsApi,
  onboarding: onboardingApi,
  lite: liteApi,
  sso: ssoApi,
  enterprise: enterpriseApi,
  knowledgeSync: knowledgeSyncApi,
  ragAdmin: ragAdminApi,
  federation: federationApi,
  agentSwarm: agentSwarmApi,
  platform: platformApi,
  verticals: verticalsApi,
}

export default api
