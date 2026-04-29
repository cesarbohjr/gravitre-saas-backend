// API Types matching FastAPI backend schemas
// Keep in sync with backend/app/operators/schemas.py, backend/app/routers/*.py

// ============ Auth & User ============
export interface User {
  id: string
  email: string
  full_name?: string
  avatar_url?: string
  role?: string
  created_at?: string
  updated_at?: string
}

export interface UserProfile {
  user: User
  organizations: Organization[]
  current_org?: Organization
}

// ============ Organization ============
export interface Organization {
  id: string
  name: string
  slug?: string
  logo_url?: string
  plan?: string
  created_at?: string
}

// ============ Operators ============
export type OperatorStatus = "draft" | "active" | "inactive"
export type SessionStatus = 
  | "idle"
  | "planning"
  | "review"
  | "awaiting_approval"
  | "executing"
  | "paused"
  | "completed"
  | "failed"
export type PlanStatus = 
  | "draft"
  | "pending_approval"
  | "approved"
  | "executing"
  | "completed"
  | "failed"
  | "cancelled"
export type ActionStatus = 
  | "requested"
  | "pending_approval"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"

export interface OperatorConnector {
  id: string
  type: string
  status: string
  environment: string
  updated_at?: string
  config: Record<string, unknown>
}

export interface OperatorVersionSummary {
  id: string
  operator_id: string
  environment: string
  version: number
  name: string
  description?: string
  role?: string
  capabilities: string[]
  config: Record<string, unknown>
  created_at?: string
}

export interface OperatorSummary {
  id: string
  name: string
  description?: string
  status: OperatorStatus
  role?: string
  capabilities: string[]
  config: Record<string, unknown>
  allowed_environments: string[]
  requires_admin: boolean
  requires_approval: boolean
  approval_roles: string[]
  active_version?: OperatorVersionSummary
}

export interface OperatorDetail extends OperatorSummary {
  system_prompt?: string
  connectors: OperatorConnector[]
  created_at?: string
  updated_at?: string
}

export interface OperatorSessionSummary {
  id: string
  operator_id: string
  operator_version_id?: string
  title: string
  status: SessionStatus
  environment: string
  current_task?: string
  created_at?: string
  updated_at?: string
}

export interface OperatorSessionDetail {
  session: OperatorSessionSummary
  operator: OperatorSummary
  latest_plan?: Record<string, unknown>
  actions: Record<string, unknown>[]
}

// ============ Agents ============
export type AgentStatus = "active" | "idle" | "processing" | "error"
export type AgentDepartment = "Marketing" | "Sales" | "Operations" | "Finance" | "Support"

export interface AgentPersonality {
  color: string
  gradient: string
  glow: string
}

export interface AgentStats {
  tasksToday: number
  successRate: number
  avgResponseTime: string
  workflowsUsing: number
}

export interface Agent {
  id: string
  name: string
  role: string
  department: AgentDepartment
  description: string
  status: AgentStatus
  personality: AgentPersonality
  stats: AgentStats
  capabilities: string[]
  permissions: string[]
  lastAction: string
  lastActionTime: string
  created_at?: string
  updated_at?: string
}

// ============ Workflows ============
export type WorkflowStatus = "draft" | "active" | "inactive" | "archived"
export type RunStatus = 
  | "pending"
  | "pending_approval"
  | "approved"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | "rejected"

export interface WorkflowVersion {
  id: string
  version: number
  created_at: string
  created_by?: string
  schema_version: string
  definition?: Record<string, unknown>
}

export interface Workflow {
  id: string
  name: string
  description?: string
  goal?: string
  status: WorkflowStatus
  stage?: string
  environment?: string
  created_at?: string
  updated_at?: string
  created_by?: string
  active_version?: WorkflowVersion
  versions?: WorkflowVersion[]
}

export interface WorkflowNode {
  id: string
  workflow_id: string
  version_id: string
  node_type: string
  title: string
  name?: string
  instruction?: string
  description?: string
  config?: Record<string, unknown>
  position?: { x: number; y: number }
  status?: string
  system_icon?: string
  system_name?: string
  has_approval_gate?: boolean
  inputs?: Record<string, unknown>[]
  outputs?: Record<string, unknown>[]
  guardrails?: Record<string, unknown>[]
  operator_id?: string
  connector_id?: string
  source_id?: string
  created_at?: string
}

export interface WorkflowEdge {
  id: string
  workflow_id: string
  version_id: string
  source_node_id: string
  target_node_id: string
  edge_type?: string
  label?: string
  condition?: Record<string, unknown>
  created_at?: string
}

export interface WorkflowSchedule {
  id: string
  workflow_id: string
  cron_expression: string
  enabled: boolean
  next_run_at?: string
  last_run_at?: string
  created_at?: string
}

// ============ Runs ============
export interface RunStep {
  id: string
  run_id: string
  node_id: string
  status: string
  started_at?: string
  completed_at?: string
  error?: string
  output?: Record<string, unknown>
}

export interface Run {
  id: string
  workflow_id: string
  workflow_name?: string
  version_id?: string
  status: RunStatus
  run_type?: string
  parameters?: Record<string, unknown>
  result?: Record<string, unknown>
  error?: string
  started_at?: string
  completed_at?: string
  created_at?: string
  created_by?: string
  environment?: string
  steps?: RunStep[]
}

// ============ Connectors ============
export type ConnectorStatus = "active" | "inactive" | "error" | "pending"

export interface Connector {
  id: string
  name: string
  vendor: string
  type?: string
  description?: string
  status: ConnectorStatus
  environment?: string
  sync_frequency?: string
  last_sync_at?: string
  created_at?: string
  updated_at?: string
  config?: Record<string, unknown>
  docs_url?: string
}

// ============ Sources ============
export type SourceStatus = "active" | "inactive" | "syncing" | "error"

export interface Source {
  id: string
  name: string
  type: string
  description?: string
  status: SourceStatus
  environment?: string
  connector_id?: string
  config?: Record<string, unknown>
  last_sync_at?: string
  document_count?: number
  created_at?: string
  updated_at?: string
}

// ============ Search ============
export interface SearchResult {
  id: string
  entity_type: "workflow" | "agent" | "connector" | "source" | "run" | "document"
  title: string
  description?: string
  highlight?: string
  score: number
  url: string
  metadata?: Record<string, unknown>
}

export interface SearchResponse {
  results: SearchResult[]
  suggestions: string[]
  totalCount: number
}

export interface SearchHistoryItem {
  id: string
  query: string
  results_count: number
  created_at: string
}

// ============ Training ============
export type TrainingDatasetType = "examples" | "documents" | "feedback"
export type TrainingDatasetStatus = "processing" | "ready" | "failed"
export type TrainingJobStatus = "queued" | "training" | "completed" | "failed"

export interface TrainingDataset {
  id: string
  name: string
  description?: string
  type: TrainingDatasetType
  status: TrainingDatasetStatus
  record_count: number
  created_by: string
  created_at: string
  updated_at?: string
}

export interface TrainingRecord {
  id: string
  dataset_id: string
  input: string
  expected_output: string
  metadata?: Record<string, unknown>
  created_at: string
}

export interface TrainingJob {
  id: string
  dataset_id: string
  dataset_name?: string
  model_base: string
  status: TrainingJobStatus
  progress: number
  metrics?: { accuracy?: number; loss?: number }
  started_at?: string
  completed_at?: string
  error?: string
  created_at: string
}

export interface CustomInstruction {
  id: string
  agent_id?: string
  agent_name?: string
  name: string
  content: string
  is_active: boolean
  created_at: string
  updated_at?: string
}

export interface TrainingDatasetListResponse {
  datasets: TrainingDataset[]
}

export interface TrainingJobListResponse {
  jobs: TrainingJob[]
}

export interface CustomInstructionListResponse {
  instructions: CustomInstruction[]
}

// ============ Audit ============
export type AuditAction =
  | "create" | "update" | "delete"
  | "execute" | "cancel" | "retry"
  | "approve" | "reject"
  | "login" | "logout"
  | "invite" | "remove"

export interface AuditLog {
  id: string
  user_id?: string
  user_name?: string
  user_email?: string
  agent_id?: string
  agent_name?: string
  action: AuditAction
  entity_type: string
  entity_id: string
  entity_name?: string
  details?: Record<string, unknown>
  ip_address?: string
  user_agent?: string
  created_at: string
}

export interface AuditListResponse {
  logs: AuditLog[]
  total: number
  hasMore: boolean
}

export interface AuditSummary {
  byAction: Record<string, number>
  byUser: { user_id: string; user_name: string; count: number }[]
  byEntityType: Record<string, number>
}

// ============ Billing ============
export type SubscriptionTier = "free" | "node" | "control" | "command"
export type SubscriptionStatus = "active" | "past_due" | "canceled" | "trialing"

export interface Subscription {
  id: string
  stripe_subscription_id?: string
  tier: SubscriptionTier
  status: SubscriptionStatus
  seat_count: number
  lite_seats: number
  current_period_start: string
  current_period_end: string
  cancel_at_period_end: boolean
  meson_addons: string[]
}

export interface Invoice {
  id: string
  stripe_invoice_id?: string
  amount_cents: number
  currency: string
  status: string
  period_start: string
  period_end: string
  pdf_url?: string
  created_at: string
}

export interface PaymentMethod {
  id: string
  type: string
  last4: string
  exp_month: number
  exp_year: number
  is_default: boolean
}

export interface BillingOverview {
  subscription: Subscription
  usage: BillingUsageResponse
  invoices: Invoice[]
  payment_methods: PaymentMethod[]
}

// ============ Metrics ============
export interface MetricsOverview {
  total_workflows: number
  active_workflows: number
  total_runs: number
  successful_runs: number
  failed_runs: number
  pending_approvals: number
  avg_run_duration_ms?: number
  runs_by_day?: { date: string; count: number }[]
  runs_by_status?: { status: string; count: number }[]
}

export interface MetricInsight {
  id: string
  type: "anomaly" | "trend" | "optimization"
  severity: "info" | "warning" | "critical" | "success"
  title: string
  description: string
  timestamp: string
  relatedWorkflowId?: string
  relatedRunId?: string
  relatedConnectorId?: string
  suggestedAction?: string
}

// ============ API Responses ============
export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

export interface OperatorListResponse {
  operators: OperatorSummary[]
}

export interface OperatorSessionListResponse {
  sessions: OperatorSessionSummary[]
}

export interface AgentListResponse {
  agents: Agent[]
}

export interface WorkflowListResponse {
  workflows: Workflow[]
}

export interface RunListResponse {
  runs: Run[]
}

export interface ConnectorListResponse {
  connectors: Connector[]
}

export interface SourceListResponse {
  sources: Source[]
}

export interface ApiKey {
  id: string
  org_id?: string
  name: string
  key_prefix: string
  status: "active" | "revoked"
  last_used_at?: string | null
  created_at?: string
  updated_at?: string
  key?: string
}

export interface ApiKeyListResponse {
  apiKeys: ApiKey[]
}

export interface LiteSeatDepartment {
  id: string
  name: string
  lite_seat_allocation: number
  used_seats: number
  available_seats: number
  department_admin_id?: string | null
  status?: string
  created_at?: string
}

export interface LiteSeatsSummary {
  included: number
  allocated: number
  used: number
}

export interface LiteSeatsResponse {
  summary: LiteSeatsSummary
  departments: LiteSeatDepartment[]
}

export interface MesonAddon {
  id: string
  code: string
  name: string
  description: string
  monthly_price_usd: number
  enabled: boolean
}

export interface MesonAddonsResponse {
  addons: MesonAddon[]
  monthly_total_usd: number
}

export interface BillingUsageResponse {
  period_start: string
  tier?: string
  totals: {
    outputs: number
    workflow_runs: number
    api_calls: number
    ai_tokens: number
  }
  included_outputs: number | null
  overage_outputs: number
  overage_cost_usd: number
}

// ============ API Requests ============
export interface CreateWorkflowRequest {
  name: string
  description?: string
  goal?: string
  environment_id?: string
}

export interface UpdateWorkflowRequest {
  name?: string
  description?: string
  goal?: string
  status?: WorkflowStatus
}

export interface CreateConnectorRequest {
  name: string
  vendor: string
  description?: string
  api_key?: string
  webhook_url?: string
  sync_frequency?: string
  environment_id?: string
}

export interface CreateSourceRequest {
  name: string
  type: string
  description?: string
  connector_id?: string
  config?: Record<string, unknown>
}

export interface ExecuteWorkflowRequest {
  workflow_id: string
  parameters?: Record<string, unknown>
}

export interface ApproveRejectRequest {
  comment?: string
}

export interface OperatorSessionCreateRequest {
  title: string
  current_task?: string
}

export interface OperatorActionPlanRequest {
  session_id: string
  primary_context: { ref_type: string; ref_id: string }
  related_contexts?: { ref_type: string; ref_id: string }[]
  operator_goal?: string
  prompt?: string
}

export interface CreateAgentRequest {
  name: string
  role: string
  department: AgentDepartment
  description?: string
  capabilities?: string[]
  permissions?: string[]
}
