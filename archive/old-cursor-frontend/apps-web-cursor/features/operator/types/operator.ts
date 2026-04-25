export type ContextPackType = "run" | "workflow" | "connector" | "source";

export type OperatorSession = {
  id: string;
  operator_id: string;
  operator_version_id?: string | null;
  title: string;
  timestamp: string;
  environment: string;
  contextEntity: string;
  primaryContext: { type: ContextPackType; id: string | null };
  status?: string;
  current_task?: string | null;
  created_at?: string | null;
};

export type Explainability = {
  data_used: string[];
  environment: string;
  permissions_required: string[];
  approval_required: boolean;
  admin_required: boolean;
  executable: boolean;
  draft_only: boolean;
  confirmation_required: boolean;
};

export type ActionPlanStep = {
  id: string;
  title: string;
  description: string;
  step_type: string;
  linked_entity?: { type: ContextPackType; id: string } | null;
  dependencies: string[];
  explanation: Explainability;
};

export type ActionPlan = {
  plan_id: string;
  title: string;
  summary: string;
  steps: ActionPlanStep[];
};

export type ActionProposal = {
  id: string;
  stepId: string;
  title: string;
  description: string;
  environment: string;
  requiresApproval: boolean;
  requiresAdmin: boolean;
  executionState: "draft" | "executable";
  confirmationRequired: boolean;
  ctaLabel: string;
};

export type ContextPack = {
  id: string | null;
  type: ContextPackType;
  title: string;
  summary: string;
  status: "ready" | "stale" | "restricted" | "missing";
  environment: string;
  href: string;
};

export type GuardrailSummary = {
  environment: string;
  approval_requirements: string[];
  admin_restrictions: string[];
  execution_restrictions: string[];
};

export type RunStepSummary = {
  step_index: number;
  step_name: string;
  step_type: string;
  status: string;
  error_code?: string | null;
};

export type RunSummary = {
  id: string;
  workflow_id: string | null;
  status: string;
  approval_status: string | null;
  approval_required: boolean;
  required_approvals: number;
  approvals_received: number;
  created_at: string | null;
  environment: string;
};

export type RunContextPack = {
  pack: ContextPack;
  run: RunSummary;
  steps: RunStepSummary[];
  recent_runs: Array<{ id: string; status: string; created_at: string | null; workflow_id: string | null }>;
  audit: { total_events: number; recent_events: Array<{ action: string; created_at: string }> };
  environment: string;
};

export type WorkflowContextPack = {
  pack: ContextPack;
  workflow: { id: string; name: string; description?: string | null; schema_version?: string | null; updated_at?: string | null };
  active_version: { id: string; version: number; created_at?: string | null } | null;
  recent_versions: Array<{ id: string; version: number; created_at?: string | null }>;
  recent_runs: Array<{ id: string; status: string; created_at: string | null; workflow_id: string | null }>;
  linked_connectors: Array<{ type: string; step_types: string[] }>;
  environment: string;
};

export type ConnectorContextPack = {
  pack: ContextPack;
  connector: { id: string; type: string; status: string; updated_at?: string | null; environment: string };
  config_summary: { keys: string[]; field_count: number };
  related_workflows: Array<{ id: string; name: string }>;
  environment: string;
};

export type SourceContextPack = {
  pack: ContextPack;
  source: { id: string; title: string; type: string; updated_at?: string | null; environment: string };
  recent_documents: Array<{ id: string; title?: string | null; updated_at?: string | null; external_id?: string | null }>;
  ingest_jobs: Array<{ id: string; status: string; created_at?: string | null; updated_at?: string | null; error_code?: string | null }>;
  environment: string;
};

export type OperatorContextPack =
  | RunContextPack
  | WorkflowContextPack
  | ConnectorContextPack
  | SourceContextPack;

export type ResearchResult = {
  id: string;
  title: string;
  items: string[];
};

export type OperatorWorkspace = {
  currentTask: string;
  reasoning: string;
  contextSummary: string;
  researchResults: ResearchResult[];
};

export type OperatorData = {
  sessions: OperatorSession[];
  actionPlan: ActionPlan | null;
  proposals: ActionProposal[];
  contextPacks: ContextPack[];
  activeContextPack: OperatorContextPack | null;
  guardrails: GuardrailSummary | null;
  workspace: OperatorWorkspace;
  isLoading: boolean;
  error: string | null;
};
