/**
 * Typed API client for FastAPI backend
 * All methods include auth headers automatically via fetcher
 */

import { apiFetch, fetcher } from "@/lib/fetcher"
import type {
  User,
  UserProfile,
  OperatorSummary,
  OperatorDetail,
  OperatorListResponse,
  OperatorSessionSummary,
  OperatorSessionDetail,
  OperatorSessionListResponse,
  OperatorSessionCreateRequest,
  OperatorActionPlanRequest,
  Agent,
  AgentListResponse,
  CreateAgentRequest,
  Workflow,
  WorkflowListResponse,
  WorkflowNode,
  WorkflowEdge,
  WorkflowSchedule,
  CreateWorkflowRequest,
  UpdateWorkflowRequest,
  Run,
  RunListResponse,
  ExecuteWorkflowRequest,
  ApproveRejectRequest,
  Connector,
  ConnectorListResponse,
  CreateConnectorRequest,
  Source,
  SourceListResponse,
  CreateSourceRequest,
  SearchResponse,
  SearchHistoryItem,
  ApiKey,
  ApiKeyListResponse,
  BillingUsageResponse,
  LiteSeatsResponse,
  MesonAddonsResponse,
  MetricsOverview,
  MetricInsight,
} from "@/types/api"

// Base URL for backend API (can be overridden via env)
const API_BASE = process.env.NEXT_PUBLIC_API_URL || ""

function apiUrl(path: string): string {
  return `${API_BASE}${path}`
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
    throw new Error(error.detail || `Request failed: ${response.status}`)
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
    throw new Error(error.detail || `Request failed: ${response.status}`)
  }
  return response.json()
}

async function deleteRequest(url: string): Promise<void> {
  const response = await apiFetch(url, { method: "DELETE" })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `Request failed: ${response.status}`)
  }
}

// ============ Auth ============
export const authApi = {
  me: () => fetcher<UserProfile>(apiUrl("/api/auth/me")),
  updateProfile: (data: Partial<User>) => patchJson<User>(apiUrl("/api/auth/me"), data),
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
}

// ============ Workflows ============
export const workflowsApi = {
  list: () => fetcher<WorkflowListResponse>(apiUrl("/api/workflows")),
  get: (id: string) => fetcher<Workflow>(apiUrl(`/api/workflows/${id}`)),
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
  
  // Execution
  execute: (data: ExecuteWorkflowRequest) => postJson<Run>(apiUrl("/api/workflows/execute"), data),
  dryRun: (data: { workflow_id?: string; definition?: unknown; parameters?: unknown }) =>
    postJson<{ run_id: string; result: unknown }>(apiUrl("/api/workflows/dry-run"), data),
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
  cancel: (id: string) => postJson<Run>(apiUrl(`/api/runs/${id}/cancel`), {}),
  retry: (id: string) => postJson<Run>(apiUrl(`/api/runs/${id}/retry`), {}),
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
}

// ============ Sources ============
export const sourcesApi = {
  list: () => fetcher<SourceListResponse>(apiUrl("/api/sources")),
  get: (id: string) => fetcher<Source>(apiUrl(`/api/sources/${id}`)),
  create: (data: CreateSourceRequest) => postJson<Source>(apiUrl("/api/sources"), data),
  update: (id: string, data: Partial<Source>) => patchJson<Source>(apiUrl(`/api/sources/${id}`), data),
  delete: (id: string) => deleteRequest(apiUrl(`/api/sources/${id}`)),
  sync: (id: string) => postJson<{ status: string }>(apiUrl(`/api/sources/${id}/sync`), {}),
}

// ============ Search ============
export const searchApi = {
  search: (query: string, filters?: { types?: string[]; dateRange?: string }) =>
    postJson<SearchResponse>(apiUrl("/api/search"), { query, filters }),
  history: () => fetcher<{ searches: SearchHistoryItem[] }>(apiUrl("/api/search/history")),
  deleteHistory: (id: string) => deleteRequest(apiUrl(`/api/search/history/${id}`)),
  clearHistory: () => deleteRequest(apiUrl("/api/search/history")),
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
  exportCsv: (range?: string) =>
    apiFetch(apiUrl(`/api/metrics/export?format=csv${range ? `&range=${range}` : ""}`)),
  workflowStats: (workflowId: string) =>
    fetcher<{ runs: number; success_rate: number; avg_duration_ms: number }>(
      apiUrl(`/api/metrics/workflows/${workflowId}`)
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

  // Meson addons
  getMesonAddons: () => fetcher<MesonAddonsResponse>(apiUrl("/api/settings/meson-addons")),
  toggleMesonAddon: (code: string, enabled: boolean) =>
    patchJson<{ subscription: Record<string, unknown> }>(apiUrl("/api/settings/meson-addons"), { code, enabled }),

  // Usage-based billing
  getBillingUsage: () => fetcher<BillingUsageResponse>(apiUrl("/api/settings/billing-usage")),
}

// ============ Environments ============
export const environmentsApi = {
  list: () =>
    fetcher<{ environments: { id: string; name: string; is_default: boolean }[] }>(apiUrl("/api/environments")),
  create: (data: { name: string }) =>
    postJson<{ id: string; name: string }>(apiUrl("/api/environments"), data),
  delete: (id: string) => deleteRequest(apiUrl(`/api/environments/${id}`)),
}

// Convenience export for all APIs
export const api = {
  auth: authApi,
  operators: operatorsApi,
  agents: agentsApi,
  workflows: workflowsApi,
  runs: runsApi,
  approvals: approvalsApi,
  connectors: connectorsApi,
  sources: sourcesApi,
  search: searchApi,
  metrics: metricsApi,
  settings: settingsApi,
  environments: environmentsApi,
}

export default api
