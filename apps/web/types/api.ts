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
export type AgentDepartment = "Marketing" | "Sales" | "Operations" | "Finance" | "Support" | "HR"

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
  referenceFolders?: AgentReferenceFolder[]
  lastAction: string
  lastActionTime: string
  created_at?: string
  updated_at?: string
}

export type AgentReferenceFolderTag =
  | "marketing"
  | "hr"
  | "operations"
  | "engineering"
  | "finance"
  | "legal"
  | "sales"
  | "general"

export interface AgentReferenceFolder {
  id: string
  connectorId: string
  connectorVendor: string
  connectorName: string
  folderPath: string
  folderName: string
  label?: string
  tags: AgentReferenceFolderTag[]
}

// ============ Workflows ============
export type WorkflowStatus = "draft" | "active" | "paused" | "inactive" | "archived" | "error"
export type RunStatus = 
  | "pending"
  | "pending_approval"
  | "awaiting_approval"
  | "approved"
  | "running"
  | "paused"
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

export type ScheduledItemKind = "workflow" | "task" | "job"

export type ScheduledItemStatus =
  | "enabled"
  | "disabled"
  | "running"
  | "queued"
  | "completed"
  | "failed"
  | "scheduled"

export interface ScheduledItem {
  kind: ScheduledItemKind
  id: string
  title: string
  subtitle?: string
  status: ScheduledItemStatus
  cron?: string
  nextRunAt?: string
  lastRunAt?: string
  startedAt?: string
  completedAt?: string
  workflowId?: string
  progress?: number
  occurrences?: string[]
}

export interface SchedulesListResponse {
  items: ScheduledItem[]
}

export interface SchedulesListParams {
  workflowId?: string
  from?: string
  to?: string
  kinds?: ScheduledItemKind[]
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
  workflowId?: string
  workflowName?: string
  version_id?: string
  status: RunStatus
  run_type?: string
  parameters?: Record<string, unknown>
  result?: Record<string, unknown>
  error?: string
  errorMessage?: string
  started_at?: string
  startedAt?: string
  completed_at?: string
  completedAt?: string
  created_at?: string
  created_by?: string
  environment?: string
  steps?: RunStep[]
  approvalStatus?: string
  approvalRequired?: boolean
  duration_ms?: number
  durationMs?: number
  triggered_by?: string
  triggeredBy?: string
  records_processed?: number
  recordsProcessed?: number
  error_message?: string
}

export interface RunDetailResponse {
  run: Run
  steps: Array<{
    id: string
    nodeId?: string | null
    name?: string
    stepType?: string
    status: string
    startedAt?: string | null
    completedAt?: string | null
    errorMessage?: string | null
    orderIndex?: number
    inputSnapshot?: Record<string, unknown> | null
    outputSnapshot?: Record<string, unknown> | null
    isRetryable?: boolean
    logs?: string[] | null
  }>
}

export interface WorkflowDryRunResponse {
  run_id: string
  status: string
  plan: Record<string, unknown>[]
  steps: Array<Record<string, unknown>>
  errors: string[]
}

export interface ExecuteWorkflowResponse {
  run_id: string
  id?: string
  status: string
  approval_required?: boolean
  queued?: boolean
  steps?: Array<Record<string, unknown>>
  errors?: string[]
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

// ============ Conversations ============
export interface Conversation {
  id: string
  title: string
  preview?: string
  created_at: string
  updated_at: string
  message_count: number
  archived_at?: string | null
}

export interface ConversationMessage {
  id: string
  conversation_id: string
  role: "user" | "assistant"
  content: string
  tool_calls?: unknown[]
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

export interface FineTunedModel {
  id: string
  name: string
  status: string
  baseModel?: string
  deployedVersion?: number
  currentVersion?: number
  fineTunedOpenAiId?: string | null
  datasetId?: string | null
  createdAt?: string
}

export interface FineTunedModelListResponse {
  models: FineTunedModel[]
}

export interface WorkflowAgent {
  id: string
  name: string
  role?: string
  model?: string
  status?: string
  trainedModelId?: string | null
}

export interface WorkflowAgentListResponse {
  agents: WorkflowAgent[]
}

export interface AgentFineTunedModelAssignment {
  agentId: string
  trainedModelId?: string | null
  baseModel?: string
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

// ============ Notifications ============
export type NotificationType =
  | "approval_needed"
  | "assignment_created"
  | "run_completed"
  | "run_failed"
  | "mention"
  | "team_invite"
  | "system"
  | "agent_created"
  | "workflow_created"
  | "task_completed"

export interface Notification {
  id: string
  type: NotificationType
  title: string
  body: string
  entity_type?: string
  entity_id?: string
  url?: string
  is_read: boolean
  is_archived: boolean
  created_at: string
}

export interface NotificationListResponse {
  notifications: Notification[]
  unread_count: number
}

export interface ActivityEvent {
  id: string
  source: string
  event_type: string
  title: string
  body: string
  status: "completed" | "failed" | "running" | string
  entity_type?: string
  entity_id?: string
  url?: string
  integration?: string
  metadata?: Record<string, unknown>
  created_at: string
}

export interface ActivityFeedResponse {
  events: ActivityEvent[]
}

// ============ Onboarding ============
export interface OnboardingStep {
  id: string
  key: string
  title: string
  description: string
  is_required: boolean
  is_completed: boolean
  order: number
}

export interface OnboardingProgress {
  current_step: number
  total_steps: number
  steps: OnboardingStep[]
  completed_at?: string
  skipped: boolean
  step_data?: Record<string, unknown>
  welcome_completed?: boolean
}

// ============ Lite Mode ============
export interface LiteTask {
  id: string
  workflow_id: string
  workflow_name: string
  status: "pending" | "processing" | "completed" | "failed"
  progress: number
  input_summary?: string
  created_at: string
  completed_at?: string
  error?: string
}

export interface LiteDeliverable {
  id: string
  task_id: string
  task_name?: string
  name: string
  type: string
  size_bytes: number
  download_url: string
  preview_url?: string
  created_at: string
}

export interface LiteQuickAction {
  id: string
  name: string
  description?: string
  workflow_id: string
  icon?: string
}

export interface LiteHomeData {
  recent_tasks: LiteTask[]
  pending_deliverables: LiteDeliverable[]
  quick_actions: LiteQuickAction[]
  stats: {
    tasks_this_week: number
    completed_this_week: number
    pending_deliverables: number
  }
}

export interface LiteResultsSummary {
  period: string
  tasks_completed: number
  success_rate: number
  avg_completion_time_hours: number
  by_workflow: { workflow_name: string; count: number }[]
}

// ============ SSO ============
export type SSOProviderType = "saml" | "oidc"

export interface SSOConfiguration {
  id: string
  org_id: string
  provider_type: SSOProviderType
  is_enabled: boolean
  saml_entity_id?: string
  saml_sso_url?: string
  oidc_issuer?: string
  oidc_client_id?: string
  auto_provision_users: boolean
  default_role: string
  allowed_domains?: string[]
  created_at: string
}

export interface SSOConfigurationCreate {
  provider_type: SSOProviderType
  saml_entity_id?: string
  saml_sso_url?: string
  saml_slo_url?: string
  saml_certificate?: string
  oidc_issuer?: string
  oidc_client_id?: string
  oidc_client_secret?: string
  oidc_authorization_endpoint?: string
  oidc_token_endpoint?: string
  oidc_userinfo_endpoint?: string
  auto_provision_users?: boolean
  default_role?: string
  allowed_domains?: string[]
}

export interface SSOInitResponse {
  redirect_url: string
  state: string
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

export interface AgentMemory {
  id: string
  agentId: string
  content: string
  category: "fact" | "preference" | "pattern" | "rule"
  provenance?: string | null
  source?: string | null
  confidence: number
  usageCount: number
  editable: boolean
  createdAt?: string
  updatedAt?: string
  score?: number
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
  workflow_runs_included?: number | null
  ai_credits_included?: number | null
  weekly_totals?: number[]
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
  apiKey?: string
  webhook_url?: string
  webhookUrl?: string
  sync_frequency?: string
  syncFrequency?: string
  environment_id?: string
  config?: Record<string, unknown>
  secrets?: Record<string, string>
}

export interface CreateSourceRequest {
  name: string
  type: string
  typeId?: string
  description?: string
  connector_id?: string
  connectionString?: string
  config?: Record<string, unknown>
}

export interface DataSourceConnectionField {
  key: string
  label: string
  type: "text" | "number" | "password" | "boolean" | "textarea" | "select"
  required?: boolean
  placeholder?: string
  default?: string | number | boolean
  options?: Array<{ value: string; label: string }>
}

export interface DataSourceTypeDefinition {
  id: string
  name: string
  category: string
  categoryLabel: string
  icon: string
  color: string
  driver: string
  connectionFields: DataSourceConnectionField[]
  oauthVendor?: string
}

export interface DataSourceTypesResponse {
  types: DataSourceTypeDefinition[]
  categories: Array<{ id: string; label: string }>
}

export interface DataSourceTestResponse {
  success: boolean
  message?: string
  tables?: number
  records?: number
  driverPending?: boolean
  schemaPreview?: Array<{ name: string; schema?: string; columns?: Array<{ name: string; type: string }> }>
  suggestions?: string[]
}

export interface DataSourceQueryResponse {
  question: string
  sql: string
  columns: string[]
  rows: Record<string, unknown>[]
  rowCount: number
  schemaTableCount?: number
}

export interface SourceSyncHistoryItem {
  id: string
  action?: string
  status: string
  records?: number
  tables?: number
  durationMs?: number
  error?: string
  trigger?: string
  createdAt?: string
}

export interface SourceConnectorOption {
  id: string
  type: string
  status: string
  name: string
  environment?: string
}

export interface SourceDetail {
  id: string
  name: string
  type: string
  typeId?: string
  status: string
  environment?: string
  description?: string
  tablesCount?: number
  recordCount?: number
  lastSyncAt?: string
  createdAt?: string
  syncIntervalSeconds?: number
  connectionHost?: string
  connectionPort?: string | number
  connectionDatabase?: string
  connectorId?: string
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
  department?: AgentDepartment
  purpose?: string
  description?: string
  model?: string
  capabilities?: string[]
  permissions?: string[]
  systems?: string[]
  guardrails?: string[]
  referenceFolders?: AgentReferenceFolder[]
  status?: string
}

// ============ Marketplace (STA-71) ============
export type PartnerSubmissionStatus =
  | "pending"
  | "in_review"
  | "approved"
  | "rejected"
  | "withdrawn"

export interface PartnerSecurityChecklist {
  noHardcodedSecrets: boolean
  oauthRedirectsDocumented: boolean
  scopesMinimized: boolean
  dataResidencyDocumented: boolean
  auditLoggingCompatible: boolean
  errorHandlingDocumented: boolean
}

export interface PartnerSecurityFinding {
  code: string
  severity: "critical" | "warning" | "info"
  message: string
  file?: string | null
  line?: number | null
}

export interface PartnerSecurityScan {
  findings: PartnerSecurityFinding[]
  filesScanned: number
  passed: boolean
  criticalCount?: number
  warningCount?: number
}

export interface PartnerScopeReviewEntry {
  actionKey: string
  declaredScopes: string[]
  recommendedScopes: string[]
  issues: string[]
}

export interface PartnerScopeReview {
  entries: PartnerScopeReviewEntry[]
  oauthScopes: string[]
  passed: boolean
  issueCount?: number
}

export type PartnerCertificationStatus = "pending" | "passed" | "failed"

export interface PartnerConnectorSubmission {
  id: string
  orgId: string
  submittedBy: string
  packageId: string
  vendor: string
  name: string
  version: string
  manifest: Record<string, unknown>
  securityChecklist: Record<string, boolean>
  packageSourceFiles?: string[]
  packageSources?: Record<string, string>
  securityScan?: PartnerSecurityScan
  scopeReview?: PartnerScopeReview
  certificationStatus?: PartnerCertificationStatus
  status: PartnerSubmissionStatus
  reviewerId?: string | null
  reviewNotes?: string | null
  reviewedAt?: string | null
  createdAt?: string
  updatedAt?: string
}

export interface MarketplaceSandboxStatus {
  provisioned: boolean
  publisherOrgId: string
  sandboxOrgId?: string
  sandboxOrgName?: string
  sandboxOrgSlug?: string
  seededAt?: string | null
  welcomeMessage?: string
  createdAt?: string
}

export interface MarketplaceSandboxProvisionResult {
  provisioned: boolean
  created?: boolean
  reset?: boolean
  publisherOrgId: string
  sandboxOrgId: string
  sandboxOrgName?: string
  sandboxOrgSlug?: string
  welcomeMessage?: string
  agentsCreated?: number
  workflowsCreated?: number
  connectorsCreated?: number
}

export interface MarketplaceSandboxAuditEntry {
  id: string
  action: string
  resourceType?: string | null
  resourceId?: string | null
  metadata?: Record<string, unknown>
  createdAt?: string
}

export interface MarketplaceSandboxDemoResult {
  sandboxOrgId: string
  agentId: string
  agentName: string
  connectorId: string
  connectorName: string
  action: string
  success: boolean
  tickets: Array<Record<string, unknown>>
  errorCode?: string | null
  errorMessage?: string | null
  auditTrail: MarketplaceSandboxAuditEntry[]
}

export interface MarketplaceConnectorPricing {
  model: "free" | "flat_monthly" | "per_invocation"
  priceCents: number
  currency: string
}

export type PrivateBundleStatus = "draft" | "active" | "disabled"

export interface PrivateConnectorBundle {
  id: string
  orgId: string
  createdBy: string
  name: string
  packageId: string
  vendor: string
  version: string
  manifest: Record<string, unknown>
  packageSourceFiles?: string[]
  signingPublicKeyPem?: string
  signatureAlgorithm?: string
  securityScan?: PartnerSecurityScan
  scopeReview?: PartnerScopeReview
  certificationStatus?: PartnerCertificationStatus
  status: PrivateBundleStatus
  activatedAt?: string | null
  activatedBy?: string | null
  createdAt?: string
  updatedAt?: string
  authType?: "oauth" | "apiKey"
  capabilities?: string[]
  runtime?: string
}

export interface MarketplaceRegistryConnector {
  id: string
  submissionId: string
  orgId: string
  packageId: string
  vendor: string
  name: string
  version: string
  manifest: Record<string, unknown>
  authType: "oauth" | "apiKey"
  description: string
  capabilities: string[]
  publishedBy: string
  publishedAt?: string
  status: string
  certificationBadge?: string | null
  certifiedAt?: string | null
  securityScanSummary?: Record<string, unknown>
  pricing?: MarketplaceConnectorPricing
}

export interface MarketplacePartnerAccount {
  connected: boolean
  connectStatus: string
  chargesEnabled: boolean
  payoutsEnabled: boolean
  detailsSubmitted: boolean
  stripeConnectAccountId?: string | null
  onboardingCompletedAt?: string | null
}

export interface MarketplaceEarningsSummary {
  grossCents: number
  platformFeeCents: number
  partnerEarningsCents: number
  transferredCents: number
  pendingTransferCents: number
  usageEventCount: number
  activeInstallCount: number
}

export interface MarketplaceAssetPayoutSummary {
  grossCents: number
  platformFeeCents: number
  partnerEarningsCents: number
  transferredCents: number
  pendingTransferCents: number
  payoutCount: number
  pendingPayoutCount?: number
  failedPayoutCount?: number
}

export interface MarketplaceAssetPayoutRow {
  id: string
  assetId?: string | null
  assetSlug?: string | null
  assetTitle?: string | null
  grossCents: number
  partnerEarningsCents: number
  status: string
  currency: string
  createdAt?: string | null
}

export interface MarketplacePublisherPayoutSyncResult {
  transferred: number
  failed: number
  pendingReviewed: number
}

export interface MarketplacePublisherEarningsBreakdown {
  grossCents: number
  platformFeeCents: number
  partnerEarningsCents: number
  transferredCents: number
  pendingTransferCents: number
  usageEventCount?: number
  activeInstallCount?: number
  payoutCount?: number
}

export interface MarketplacePublisherAdoptionSummary {
  publishedAssets: number
  totalInstalls: number
  usageEventCount: number
  paidSaleCount: number
}

export interface MarketplaceTopEarningAsset {
  assetId: string
  slug?: string | null
  title?: string | null
  assetType?: string | null
  grossCents: number
  partnerEarningsCents: number
  saleCount: number
}

export interface MarketplacePublisherRevenueAnalytics {
  partnerOrgId: string
  earnings: {
    combined: MarketplacePublisherEarningsBreakdown
    connectorUsage: MarketplacePublisherEarningsBreakdown
    assetSales: MarketplacePublisherEarningsBreakdown
  }
  adoption: MarketplacePublisherAdoptionSummary
  topAssetsByEarnings: MarketplaceTopEarningAsset[]
  recentAssetPayouts: MarketplaceAssetPayoutRow[]
  recentUsageEvents: MarketplaceUsageEvent[]
  platformTopAssets?: MarketplaceTopEarningAsset[]
}

export interface MarketplaceUsageEvent {
  id: string
  action: string
  grossCents: number
  partnerEarningsCents: number
  transferStatus: string
  customerOrgId: string
  createdAt?: string
}

export interface MarketplacePartnerPricing {
  id: string | null
  registryId: string
  partnerOrgId: string
  pricingModel: "free" | "flat_monthly" | "per_invocation"
  priceCents: number
  currency: string
  platformFeeBps: number
  stripePriceId?: string | null
  active: boolean
  vendor?: string | null
  connectorName?: string | null
  updatedAt?: string | null
}

export interface MarketplaceBillingStatus {
  partnerOrgId: string
  account: MarketplacePartnerAccount
  pricingCount: number
  earnings: MarketplaceEarningsSummary
  assetPayouts?: MarketplaceAssetPayoutSummary
  recentAssetPayouts?: MarketplaceAssetPayoutRow[]
  platformFeeBps: number
  recentUsage: MarketplaceUsageEvent[]
}

// ============ Enterprise Admin ============

export type EnterpriseRegion = "us" | "eu"

export interface EnterpriseDataRegion {
  region: EnterpriseRegion
  storagePrefix: string
}

export interface EnterpriseBranding {
  logoUrl: string | null
  primaryColor: string | null
  customDomain: string | null
  customDomainVerified: boolean
  hidePoweredBy: boolean
  emailFromName: string | null
}

export interface EnterpriseDnsRecord {
  type: "CNAME" | "TXT"
  host: string
  value: string
  ttl?: number | null
}

export interface EnterpriseDomainInstructions {
  domain: string | null
  records: EnterpriseDnsRecord[]
}

export interface EnterpriseDomainVerifyCheck {
  ok: boolean
  expected?: string | null
  found?: string | null
  message?: string | null
}

export interface EnterpriseDomainVerifyResult {
  verified: boolean
  method: string
  checks: {
    cname?: EnterpriseDomainVerifyCheck
    txt?: EnterpriseDomainVerifyCheck
  }
}

export interface EnterpriseWorkforceAnalytics {
  tasksCompleted: number
  tasksFailed: number
  tasksRunning: number
  handoffs: number
  toolSuccessRate: number
  approvalWaitEvents: number
  slaBreaches: number
}

export interface EnterpriseCostAttribution {
  totalCostUsd: number
  byAgent: Record<string, number>
  byDepartment: Record<string, number>
  byWorkflow: Record<string, number>
}

export interface EnterpriseSiemConfig {
  enabled: boolean
  endpoint: string | null
  hasSecret: boolean
}

export interface EnterpriseSiemTestResult {
  ok: boolean
  status?: number | null
  message?: string | null
}

// CS Command Center — integration health (STA-124)
export type IntegrationHealthGrade = "healthy" | "at_risk" | "critical"

export interface IntegrationHealthDimension {
  score: number
  label: string
  summary: string
  activeConnectors?: number
  totalConnectors?: number
  activePct?: number
  successRate?: number | null
  utilizationRate?: number | null
  avgLatencyMinutes?: number | null
  p95LatencyMinutes?: number | null
  pendingApprovals?: number
}

export interface IntegrationHealthRisk {
  dimension: string
  score: number
  summary?: string
  severity: "high" | "medium"
}

export interface IntegrationHealthScore {
  score: number
  grade: IntegrationHealthGrade
  dimensions: Record<string, IntegrationHealthDimension>
  risks: IntegrationHealthRisk[]
  weights: Record<string, number>
  lookbackDays: number
  computedAt: string
}

export interface IntegrationHealthSnapshot {
  id: string
  orgId: string
  score: number
  grade: IntegrationHealthGrade
  dimensions: Record<string, IntegrationHealthDimension>
  risks: IntegrationHealthRisk[]
  lookbackDays: number
  recordedAt: string
}

export interface IntegrationHealthHistoryResponse {
  snapshots: IntegrationHealthSnapshot[]
  count: number
}

export interface IntegrationSuggestion {
  id: string
  suggestionType: "connect_connector" | "install_department_pack" | "automate_workflow"
  connectorType?: string | null
  packId?: string | null
  title: string
  message: string
  evidence: Record<string, unknown>
  confidence: number
  priority: number
  status: string
  suggestedAt?: string
}

export interface IntegrationSuggestionsResponse {
  suggestions: IntegrationSuggestion[]
  count: number
}

export interface IntegrationSuggestionScanResponse {
  lookbackDays: number
  usage: Record<string, unknown>
  suggestionCount: number
  suggestions: IntegrationSuggestion[]
  scannedAt: string
}

export interface IntegrationSuggestionApplyResponse {
  suggestion: IntegrationSuggestion
  workflowId?: string | null
  redirectPath?: string | null
  installResult?: Record<string, unknown> | null
  applySummary?: IntegrationSuggestionApplySummary | null
}

export interface IntegrationSuggestionApplySummary {
  suggestionType?: string
  title?: string
  entities?: Array<{ type: string; id: string; label?: string | null }>
  evidenceHighlights?: string[]
  redirectPath?: string | null
}

export interface PlatformCsAlertItem {
  id: string
  orgId: string
  orgName: string
  kind: "failure" | "suggestion"
  severity?: string | null
  title?: string | null
  message?: string | null
  workflowId?: string | null
  alertType?: string | null
  suggestionType?: string | null
  priority?: number | null
  occurredAt?: string | null
}

export interface PlatformCsAlertsResponse {
  alerts: PlatformCsAlertItem[]
  count: number
}

export interface PlatformCsEscalateResponse {
  orgId: string
  orgName: string
  delivered: boolean
  deliveryError?: string | null
  deepLink?: string | null
  note?: string | null
  escalatedAt?: string
}

export interface PlatformCsTenantSummary {
  orgId: string
  name: string
  slug?: string | null
  createdAt?: string | null
  healthScore?: number | null
  healthGrade?: "healthy" | "at_risk" | "critical" | null
  healthRecordedAt?: string | null
  lookbackDays?: number | null
  riskCount: number
  openSuggestions: number
  activeFailureAlerts: number
  assignedTo?: string | null
  assignedEmail?: string | null
  assignedAt?: string | null
  snoozedUntil?: string | null
  isSnoozed?: boolean
  queueNote?: string | null
  needsAttention?: boolean
}

export interface PlatformCsWorkspaceResponse {
  tenants: PlatformCsTenantSummary[]
  summary: {
    total: number
    healthy: number
    atRisk: number
    critical: number
    noSnapshot: number
    needsAttention?: number
  }
}

export interface PlatformCsSnapshotBackfillResponse {
  requested: number
  backfilled: number
  lookbackDays: number
  results: Array<{
    orgId: string
    score?: number | null
    grade?: string | null
    snapshotId?: string | null
  }>
  errors: Array<{ orgId: string; message: string }>
}

export interface PlatformCsTenantQueueActionResponse {
  queue: {
    orgId: string
    assignedTo?: string | null
    assignedEmail?: string | null
    assignedAt?: string | null
    snoozedUntil?: string | null
    isSnoozed?: boolean
    note?: string | null
    snoozeHours?: number
  }
}

export interface WorkflowFailureAlert {
  id: string
  workflowId: string
  stepId?: string | null
  connectorId?: string | null
  alertType: string
  severity: "low" | "medium" | "high" | "critical"
  title: string
  message: string
  confidence: number
  status: string
  predictedAt?: string
}

export interface WorkflowFailureAlertsResponse {
  alerts: WorkflowFailureAlert[]
  count: number
}

export interface WorkflowFailurePredictionScanResponse {
  workflowId: string
  alertCount: number
  riskScore: number
  alerts: WorkflowFailureAlert[]
  scannedAt: string
  environment: string
}

export interface OrgFailurePredictionScanResponse {
  workflowCount: number
  scannedCount: number
  alertCount: number
  riskScore: number
  workflows: Array<{
    workflowId: string
    workflowName?: string | null
    alertCount: number
    riskScore: number
  }>
  alerts: WorkflowFailureAlert[]
  errors: Array<{
    workflowId: string
    workflowName?: string | null
    code?: string
    message: string
  }>
  scannedAt: string
  environment: string
}

export interface WorkflowDigitalTwinResponse {
  run_id: string
  status: string
  plan: Record<string, unknown>[]
  steps: Record<string, unknown>[]
  errors: string[]
  simulationMode?: string
  fixtureHits?: number
  llmPredictions?: number
  ragReads?: number
}

export interface KnowledgeSyncJob {
  id: string
  connector_id: string
  source_type: string
  status: string
  trigger_type: string
  scheduled_at?: string | null
  started_at?: string | null
  completed_at?: string | null
  pages_synced?: number | null
  ingest_jobs_queued?: number | null
  chunks_added?: number | null
  error_message?: string | null
  created_at?: string
}

export interface KnowledgeSyncJobsResponse {
  jobs: KnowledgeSyncJob[]
}

export interface KnowledgeSyncTriggerResponse {
  connector_id: string
  job_id?: string
  status?: string
  message?: string
}

// Autonomous run budgets (enterprise budgets tab)
export interface AutonomousRunBudgetLimits {
  maxActionsPerDay: number | null
  maxTokensPerDay: number | null
  maxSpendUsdPerDay: number | null
}

export interface AutonomousRunBudgetUsage {
  actions: number
  tokens: number
  spendUsd: number
}

export interface AgentAutonomousRunBudgetStatus {
  agentId: string
  name: string
  executionMode: string
  limits: AutonomousRunBudgetLimits
  usageToday: AutonomousRunBudgetUsage
  usageDate: string
}

export interface EnterpriseAutonomousRunBudgets {
  orgDefaults: AutonomousRunBudgetLimits
  agents: AgentAutonomousRunBudgetStatus[]
}

// HIPAA compliance status (enterprise hipaa tab)
export interface EnterpriseHipaaStatus {
  enabled: boolean
  baaAccepted: boolean
  baaVersion: string | null
  baaAcceptedAt: string | null
  baaAcceptedBy: string | null
  requiredBaaVersion: string
  dataRegion: string
  hipaaReady: boolean
  phiCapableConnectorCount: number
  blockedActionsWhenInactive: string[]
}

// Decision transparency logs (enterprise transparency tab)
export interface EnterpriseTransparencyLog {
  id: string
  createdAt: string
  updatedAt: string
  decisionSource: string
  operatorId: string | null
  operatorSessionId: string | null
  actionPlanId: string | null
  workflowRunId: string | null
  actorId: string | null
  inputContext: Record<string, unknown>
  modelInfo: Record<string, unknown>
  toolsInvoked: Array<Record<string, unknown>>
  humanOverride: Record<string, unknown> | null
  outcome: Record<string, unknown>
  status: string
}

export interface EnterpriseTransparencyLogsResponse {
  decisions: EnterpriseTransparencyLog[]
  count: number
}

export interface EnterpriseTransparencyExport {
  orgId: string
  generatedAt: string
  window: { from: string | null; to: string | null }
  regulation: string
  decisions: EnterpriseTransparencyLog[]
  summary: {
    decisionCount: number
    completed: number
    failed: number
    pendingApproval: number
    withHumanOverride: number
  }
}

// Unified marketplace assets (MKT-5 / MKT-6)
export interface MarketplaceConnectorChecklistItem {
  connectorType: string
  label: string
  required: boolean
  connected: boolean
  connectPath: string
  action_url?: string
  ready: boolean
}

export interface MarketplaceInstallBlocker {
  connector: string
  reason: string
  action_url: string
}

export interface MarketplaceAssetSummary {
  id: string
  slug: string
  title: string
  description?: string | null
  assetType: string
  category?: string | null
  department?: string | null
  tags: string[]
  visibility?: string | null
  orgId?: string | null
  status?: string | null
  pricingType: string
  priceCents?: number
  canInstall: boolean
  installed: boolean
  installedAt?: string | null
  connectorChecklist: MarketplaceConnectorChecklistItem[]
  connectorsReady: boolean
  requiredConnectorsConnected: number
  requiredConnectorsTotal: number
  requiresPayment?: boolean
  hasEntitlement?: boolean
  packItems?: MarketplacePackItem[]
  installCount?: number
  averageRating?: number | null
  reviewCount?: number
  featured?: boolean
  verified?: boolean
  reviewScope?: string | null
  reviewFeedback?: string | null
  publisherDisplayName?: string | null
  publisherSlug?: string | null
  publisherWebsiteUrl?: string | null
  publisherVerified?: boolean
  businessOutcome?: string | null
  useCase?: string | null
  estimatedHoursSaved?: number | null
  currentVersion?: number | null
  partnerRegistryId?: string | null
  source?: string | null
  federated?: boolean
  registryId?: string
  vendor?: string
}

export interface MarketplaceAssetsListResponse {
  assets: MarketplaceAssetSummary[]
  total: number
  limit: number
  offset: number
}

export interface MarketplacePublisherProfile {
  id: string
  slug: string
  displayName: string
  description?: string | null
  logoUrl?: string | null
  websiteUrl?: string | null
  verified: boolean
  status: string
  orgId?: string | null
  publicPublishingEnabled: boolean
  onboardedAt?: string | null
  createdAt?: string
  updatedAt?: string
}

export interface MarketplaceAssetInstallResult {
  installed: boolean
  assetId: string
  slug?: string
  assetType?: string
  entities?: Record<string, unknown>
  connectorChecklist?: MarketplaceConnectorChecklistItem[]
}

export interface MarketplaceAssetInstallCheck {
  canInstall: boolean
  blockers: MarketplaceInstallBlocker[]
  connectorChecklist: MarketplaceConnectorChecklistItem[]
  connectorsReady?: boolean
  requiredConnectorsConnected?: number
  requiredConnectorsTotal?: number
  requiresPayment?: boolean
  hasEntitlement?: boolean
  pricingType?: string
  priceCents?: number
  currency?: string
}

export interface MarketplaceAssetEntitlementStatus {
  requiresPayment: boolean
  hasEntitlement: boolean
  pricingType: string
  priceCents: number
  currency: string
}

export interface MarketplaceAssetCheckoutResult {
  checkoutUrl: string
  sessionId: string
  entitlementId: string
  mode: string
}

export interface MarketplaceRoiAssetRow {
  assetId: string
  installId: string
  slug?: string | null
  title?: string | null
  estimatedHoursSaved: number
  realizedHoursSaved: number
  usageEvents: number
  installedAt?: string | null
  businessOutcome?: string | null
  useCase?: string | null
}

export interface MarketplaceRoiSummary {
  orgId: string
  activeInstalls: number
  assetsWithUsage: number
  totalUsageEvents: number
  totalEstimatedHoursSaved: number
  totalRealizedHoursSaved: number
  realizationRate: number
  byAsset: MarketplaceRoiAssetRow[]
}

export interface MarketplaceFederatedConnectorSummary extends MarketplaceAssetSummary {
  source?: string
  registryId?: string
  vendor?: string
  federated?: boolean
  currency?: string
}

export interface MarketplacePackItemChild {
  id: string
  slug: string
  title: string
  assetType: string
  category?: string | null
  department?: string | null
}

export interface MarketplacePackItem {
  sortOrder: number
  required: boolean
  child: MarketplacePackItemChild
}

export interface MarketplaceAssetDetail extends MarketplaceAssetSummary {
  config?: Record<string, unknown>
  blockers?: MarketplaceInstallBlocker[]
  packItems?: MarketplacePackItem[]
  installVariables?: unknown[]
}

export interface MarketplaceFacetCount {
  key: string
  count: number
}

export interface MarketplaceCategoriesResponse {
  categories: MarketplaceFacetCount[]
  departments: MarketplaceFacetCount[]
  assetTypes: MarketplaceFacetCount[]
  totalAssets: number
}

export interface MarketplaceAnalyticsSummary {
  catalog: {
    totalAssets: number
    byCategory: MarketplaceFacetCount[]
    byDepartment: MarketplaceFacetCount[]
    byAssetType: MarketplaceFacetCount[]
    totalInstallCount: number
    totalCloneCount: number
  }
  org: {
    activeInstalls: number
    savedAssets: number
    reviewsSubmitted: number
    usageEvents: number
    topAssetsByUsage: {
      assetId: string
      slug?: string | null
      title?: string | null
      usageEvents: number
    }[]
  }
}

export interface MarketplaceReview {
  id: string
  assetId: string
  rating: number
  title?: string | null
  body?: string | null
  createdAt?: string
  updatedAt?: string
  mine?: boolean
}

export interface MarketplaceReviewsResponse {
  assetId: string
  reviews: MarketplaceReview[]
  myReview: MarketplaceReview | null
  total: number
  limit: number
  offset: number
}

export interface MarketplaceSaveEntry {
  id: string
  assetId: string
  createdAt?: string
  asset?: MarketplaceAssetSummary
}

export interface MarketplaceSavesListResponse {
  saves: MarketplaceSaveEntry[]
  total: number
  limit: number
  offset: number
}

export interface MarketplaceAssetCloneResult {
  cloned: boolean
  sourceAssetId: string
  asset: {
    id: string
    slug: string
    title: string
    assetType: string
    status: string
    visibility: string
    clonedFromAssetId?: string | null
  }
}

export interface MarketplaceInstallDeepLink {
  label: string
  entityType: string
  entityId: string
  path: string
}

export interface MarketplaceInstall {
  id: string
  assetId: string
  assetVersion?: string | null
  status: string
  installedEntityType?: string | null
  installedEntityId?: string | null
  installedAt?: string | null
  updatedAt?: string | null
  metadata?: {
    agentIds?: string[]
    workflowIds?: string[]
    ragSourceIds?: string[]
    operatorId?: string
  }
  deepLinks: MarketplaceInstallDeepLink[]
  asset?: {
    id: string
    slug: string
    title: string
    assetType: string
    category?: string | null
    department?: string | null
  } | null
}

export interface MarketplaceInstallsListResponse {
  installs: MarketplaceInstall[]
  total: number
  limit: number
  offset: number
}

// Federation & B2B (STA-115/116/117/118)
export type FederationPartnershipStatus =
  | "pending_partner"
  | "active"
  | "rejected"
  | "revoked"

export interface FederationPartnership {
  id: string
  orgAId: string
  orgBId: string
  currentOrgId: string
  partnerOrgId: string
  invitedByOrgId: string
  status: FederationPartnershipStatus
  initiatorConsentAt: string | null
  partnerConsentAt: string | null
  createdAt: string | null
  updatedAt: string | null
}

export type FederationHandoffStatus =
  | "pending_receiver"
  | "accepted"
  | "rejected"
  | "completed"
  | "failed"

export interface FederationHandoff {
  id: string
  partnershipId: string
  senderOrgId: string
  receiverOrgId: string
  fromAgentId: string | null
  toAgentId: string | null
  briefing: Record<string, unknown>
  message: string | null
  status: FederationHandoffStatus
  createdAt: string | null
  acceptedAt: string | null
  completedAt: string | null
}

export interface CreateFederationHandoffRequest {
  receiverOrgId: string
  fromAgentId?: string
  toAgentId?: string
  message?: string
  briefing?: Record<string, unknown>
  parameters?: Record<string, unknown>
  sourceOutput?: Record<string, unknown>
}

export interface CreateFederationConnectorGrantRequest {
  granteeOrgId: string
  connectorId: string
  allowedActions: string[]
  label?: string
  expiresInHours?: number
}

export interface CreateFederationDelegatedTaskRequest {
  delegateOrgId: string
  title: string
  instructions?: string
  payload?: Record<string, unknown>
  parentReference?: Record<string, unknown>
  delegatorAgentId?: string
  delegateAgentId?: string
}

export interface FederationConnectorGrant {
  id: string
  partnershipId?: string | null
  grantorOrgId: string
  granteeOrgId: string
  connectorId: string
  label: string | null
  allowedActions: string[]
  status: string
  expiresAt: string | null
  createdAt: string | null
}

export interface FederationDelegatedTask {
  id: string
  delegatorOrgId: string
  delegateOrgId: string
  title: string
  instructions: string | null
  status: string
  createdAt: string | null
  completedAt: string | null
}

// Agent interrupts (STA-108 / STA-170)
export type AgentInterruptTargetType = "agent_job" | "workflow_run" | "operator_session"
export type AgentInterruptSignal = "pause" | "cancel"

export interface AgentInterruptRequest {
  targetType: AgentInterruptTargetType
  targetId: string
  signal: AgentInterruptSignal
}

export interface AgentInterrupt {
  id: string
  targetType: AgentInterruptTargetType
  targetId: string
  signal: AgentInterruptSignal
  status: string
  source?: string | null
  createdAt?: string | null
}

// ML model registry (/api/ml)
export type MlModelType = "classifier" | "fine_tuned_llm" | "anomaly_detector" | "forecaster"
export type MlModelStatus =
  | "draft"
  | "training"
  | "validating"
  | "ready"
  | "deployed"
  | "failed"
  | "archived"

export interface MlModelSummary {
  id: string
  name: string
  description?: string | null
  modelType: MlModelType
  status: MlModelStatus
  currentVersion: number
  deployedVersion?: number | null
  datasetId?: string | null
  baseModel?: string | null
  createdAt?: string
  updatedAt?: string
}

export interface MlModelVersion {
  version: number
  metrics?: Record<string, unknown>
  artifactSizeBytes?: number | null
  createdAt?: string
}

export interface MlModelDetail extends MlModelSummary {
  taskType?: string | null
  versions: MlModelVersion[]
}

export interface MlModelListResponse {
  models: MlModelSummary[]
}

export interface CreateMlModelRequest {
  name: string
  model_type: MlModelType
  description?: string
  dataset_id?: string
  base_model?: string
  task_type?: string
}

export interface MlPredictRequest {
  inputs: Record<string, unknown>[]
  version?: number
  return_probabilities?: boolean
}

export interface MlPredictResponse {
  modelId: string
  version: number
  predictions: unknown[]
  probabilities?: Record<string, number>[] | null
  latencyMs?: number
}

export interface RunCompensationSummary {
  runId: string
  compensated: number
  failed: number
  skipped: number
  results: Array<{
    recordId: string
    action: string
    status: string
    error?: string | null
  }>
}

export interface ResumeGraphRunRequest {
  decision: "approved" | "rejected"
  comment?: string | null
}

export interface ApprovalBatchItemView {
  itemKey: string
  label: string
  sourceNodeId?: string | null
  routeToNodeId?: string | null
  status: "pending" | "approved" | "rejected"
  rejectComment?: string | null
  payload?: Record<string, unknown>
}

export interface ApprovalBatchView {
  batchId: string
  runId: string
  nodeId: string
  status: string
  items: ApprovalBatchItemView[]
}

export interface ApprovalBatchDecideRequest {
  decisions: Array<{
    itemKey: string
    decision: "approved" | "rejected"
    comment?: string | null
    routeToNodeId?: string | null
  }>
  resume?: boolean
}

// Agent swarm (STA-119)
export type AgentSwarmRunStatus =
  | "pending"
  | "running"
  | "aggregating"
  | "completed"
  | "failed"
  | "cancelled"

export type AgentSwarmSubtaskStatus = "queued" | "running" | "completed" | "failed" | "cancelled"

export type AgentSwarmDecisionMethod =
  | "majority_vote"
  | "unanimous"
  | "weighted_vote"
  | "chair_decides"

export interface AgentSwarmSubtask {
  id: string
  swarmRunId: string
  agentId: string
  taskPrompt: string
  scopedTools: Record<string, unknown>[]
  sortOrder: number
  status: AgentSwarmSubtaskStatus
  agentJobId: string | null
  result: Record<string, unknown> | null
  errorMessage: string | null
  executionVerified?: boolean
  createdAt: string | null
  completedAt: string | null
}

export interface AgentSwarmRun {
  id: string
  orgId: string
  parentAgentId: string | null
  objective: string
  status: AgentSwarmRunStatus
  decisionMethod: AgentSwarmDecisionMethod
  councilSessionId: string | null
  finalRecommendation: string | null
  finalConfidence: number | null
  aggregateResult: Record<string, unknown>
  errorMessage: string | null
  executionVerified?: boolean
  createdAt: string | null
  updatedAt: string | null
  completedAt: string | null
  subtasks?: AgentSwarmSubtask[]
}

export interface AgentSwarmStartRequest {
  parentAgentId: string
  objective: string
  subtasks: Array<{
    agentId: string
    task: string
    scopedTools?: Record<string, unknown>[]
  }>
  decisionMethod?: AgentSwarmDecisionMethod
}

export interface AgentSwarmListResponse {
  runs: AgentSwarmRun[]
}
