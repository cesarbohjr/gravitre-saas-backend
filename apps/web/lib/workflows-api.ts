/**
 * FE-10: Client helpers for workflow API (same-origin). Pass token from useAuth().
 * No direct FastAPI calls from browser.
 */

import { getEnvironmentHeader } from "@/lib/environment";

const API = "/api/workflows";

export type WorkflowListItem = {
  id: string;
  name: string;
  schema_version: string;
  updated_at: string;
};

export type WorkflowDetail = {
  id: string;
  name: string;
  description: string | null;
  definition: Record<string, unknown>;
  schema_version: string;
  created_at: string;
  updated_at: string;
};

export type StepOut = {
  id: string;
  step_id: string;
  step_index: number;
  step_name: string;
  step_type: string;
  status: string;
  input_snapshot: Record<string, unknown> | null;
  output_snapshot: Record<string, unknown> | null;
  error_code: string | null;
  error_message: string | null;
  is_retryable: boolean;
  started_at: string | null;
  completed_at: string | null;
};

export type DryRunResponse = {
  run_id: string;
  status: string;
  plan: Array<{ step_id: string; step_name: string }>;
  steps: StepOut[];
  errors: string[];
};

export type ExecuteResponse = {
  run_id: string;
  status: string;
  approval_required?: boolean;
  approval_status?: string;
  required_approvals?: number;
  approvals_received?: number;
  errors?: string[];
};

export type RunDetail = {
  id: string;
  workflow_id: string | null;
  run_type: string;
  status: string;
  triggered_by: string;
  trigger_type?: string | null;
  schedule_id?: string | null;
  rollback_of_run_id?: string | null;
  definition_snapshot: Record<string, unknown>;
  parameters: Record<string, unknown> | null;
  run_hash: string;
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
  steps: StepOut[];
  approval_required?: boolean;
  approval_status?: string | null;
  required_approvals?: number | null;
  approvals_received?: number | null;
  approver_roles?: string[] | null;
  workflow_version_id?: string | null;
};

export type WorkflowSchedule = {
  id: string;
  workflow_id: string;
  cron_expression: string;
  enabled: boolean;
  next_run_at: string | null;
  created_at?: string;
  updated_at?: string;
};

export type WorkflowNode = {
  id: string;
  workflow_id: string;
  node_type: "agent" | "task" | "connector" | "tool" | "source";
  title: string;
  instruction?: string | null;
  operator_id?: string | null;
  connector_id?: string | null;
  source_id?: string | null;
  tool_type?: string | null;
  tool_config?: Record<string, unknown> | null;
  position?: { x: number; y: number } | null;
  metadata?: Record<string, unknown> | null;
  environment?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type WorkflowEdge = {
  id: string;
  workflow_id: string;
  from_node_id: string;
  to_node_id: string;
  edge_type: "sequence" | "branch" | "condition";
  condition?: Record<string, unknown> | null;
  environment?: string | null;
  created_at?: string | null;
};

export type RunListItem = {
  id: string;
  workflow_id: string | null;
  workflow_name: string | null;
  run_type: string | null;
  status: string | null;
  approval_status: string | null;
  trigger_type?: string | null;
  schedule_id?: string | null;
  rollback_of_run_id?: string | null;
  required_approvals?: number | null;
  created_at: string | null;
  completed_at: string | null;
  environment?: string | null;
  triggered_by?: string | null;
};

export type WorkflowVersionItem = {
  id: string;
  version: number;
  created_at: string;
  created_by: string | null;
  schema_version: string;
};

export type ActiveWorkflowVersion = {
  id: string;
  version: number;
  created_at: string;
  created_by: string | null;
  schema_version: string;
  definition: Record<string, unknown>;
};

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function headers(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
    "X-Environment": getEnvironmentHeader(),
  };
}

export async function fetchWorkflows(token: string): Promise<{ workflows: WorkflowListItem[] }> {
  const res = await fetch(API, { headers: headers(token), cache: "no-store" });
  if (!res.ok) throw new Error(res.status === 401 ? "Unauthorized" : res.status === 503 ? "Backend unavailable" : "Request failed");
  return res.json();
}

export async function fetchWorkflow(token: string, id: string): Promise<WorkflowDetail> {
  const res = await fetch(`${API}/${id}`, { headers: headers(token), cache: "no-store" });
  if (!res.ok) throw new Error(res.status === 404 ? "Not found" : res.status === 401 ? "Unauthorized" : "Request failed");
  return res.json();
}

export async function postDryRun(
  token: string,
  body: { workflow_id?: string; definition?: Record<string, unknown>; parameters?: Record<string, unknown> }
): Promise<DryRunResponse> {
  const res = await fetch(`${API}/dry-run`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? (res.status === 503 ? "Backend unavailable" : "Request failed"));
  }
  return res.json();
}

export async function postExecute(
  token: string,
  body: { workflow_id: string; parameters?: Record<string, unknown> }
): Promise<ExecuteResponse> {
  const res = await fetch(`/api/v1/workflows/execute`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? (res.status === 503 ? "Backend unavailable" : "Request failed"));
  }
  return res.json();
}

export async function fetchRun(token: string, runId: string): Promise<RunDetail> {
  const res = await fetch(`${API}/runs/${runId}`, { headers: headers(token), cache: "no-store" });
  if (!res.ok) throw new Error(res.status === 404 ? "Not found" : res.status === 401 ? "Unauthorized" : "Request failed");
  return res.json();
}

export async function rollbackRun(token: string, runId: string): Promise<{ run_id: string; status: string }> {
  const res = await fetch(`/api/v1/workflows/runs/${runId}/rollback`, {
    method: "POST",
    headers: headers(token),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? "Request failed");
  }
  return res.json();
}

export async function fetchRuns(
  token: string,
  params: {
    status?: string;
    approval_status?: string;
    workflow_id?: string;
    run_type?: string;
    start_at?: string;
    end_at?: string;
    limit?: number;
  } = {}
): Promise<{ runs: RunListItem[] }> {
  const search = new URLSearchParams();
  if (params.status) search.set("status", params.status);
  if (params.approval_status) search.set("approval_status", params.approval_status);
  if (params.workflow_id) search.set("workflow_id", params.workflow_id);
  if (params.run_type) search.set("run_type", params.run_type);
  if (params.start_at) search.set("start_at", params.start_at);
  if (params.end_at) search.set("end_at", params.end_at);
  if (params.limit) search.set("limit", String(params.limit));
  const suffix = search.toString() ? `?${search.toString()}` : "";
  const res = await fetch(`${API}/runs${suffix}`, { headers: headers(token), cache: "no-store" });
  if (!res.ok) throw new Error(res.status === 401 ? "Unauthorized" : "Request failed");
  return res.json();
}

export async function fetchWorkflowNodes(
  token: string,
  workflowId: string
): Promise<{ nodes: WorkflowNode[] }> {
  const res = await fetch(`${API}/${workflowId}/nodes`, {
    headers: headers(token),
    cache: "no-store",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? "Request failed");
  }
  return res.json();
}

export async function createWorkflowNode(
  token: string,
  workflowId: string,
  payload: Omit<WorkflowNode, "id" | "workflow_id" | "created_at" | "updated_at" | "environment">
): Promise<WorkflowNode> {
  const res = await fetch(`${API}/${workflowId}/nodes`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? "Request failed");
  }
  return res.json();
}

export async function updateWorkflowNode(
  token: string,
  nodeId: string,
  payload: Partial<WorkflowNode>
): Promise<WorkflowNode> {
  const res = await fetch(`${API}/nodes/${nodeId}`, {
    method: "PATCH",
    headers: headers(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? "Request failed");
  }
  return res.json();
}

export async function deleteWorkflowNode(token: string, nodeId: string): Promise<void> {
  const res = await fetch(`${API}/nodes/${nodeId}`, {
    method: "DELETE",
    headers: headers(token),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? "Request failed");
  }
}

export async function fetchWorkflowEdges(
  token: string,
  workflowId: string
): Promise<{ edges: WorkflowEdge[] }> {
  const res = await fetch(`${API}/${workflowId}/edges`, {
    headers: headers(token),
    cache: "no-store",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? "Request failed");
  }
  return res.json();
}

export async function createWorkflowEdge(
  token: string,
  workflowId: string,
  payload: Omit<WorkflowEdge, "id" | "workflow_id" | "created_at" | "environment">
): Promise<WorkflowEdge> {
  const res = await fetch(`${API}/${workflowId}/edges`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? "Request failed");
  }
  return res.json();
}

export async function deleteWorkflowEdge(token: string, edgeId: string): Promise<void> {
  const res = await fetch(`${API}/edges/${edgeId}`, {
    method: "DELETE",
    headers: headers(token),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? "Request failed");
  }
}

export async function fetchWorkflowVersions(
  token: string,
  workflowId: string
): Promise<{ versions: WorkflowVersionItem[] }> {
  const res = await fetch(`/api/v1/workflows/${workflowId}/versions`, {
    headers: headers(token),
    cache: "no-store",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? "Request failed");
  }
  return res.json();
}

export async function createWorkflowVersion(token: string, workflowId: string): Promise<WorkflowVersionItem> {
  const res = await fetch(`/api/v1/workflows/${workflowId}/versions`, {
    method: "POST",
    headers: headers(token),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function activateWorkflowVersion(
  token: string,
  workflowId: string,
  versionId: string
): Promise<{ active_version_id: string; version: number }> {
  const res = await fetch(`/api/v1/workflows/${workflowId}/versions/${versionId}/activate`, {
    method: "POST",
    headers: headers(token),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function fetchActiveWorkflowVersion(
  token: string,
  workflowId: string
): Promise<ActiveWorkflowVersion> {
  const res = await fetch(`/api/v1/workflows/${workflowId}/active`, {
    headers: headers(token),
    cache: "no-store",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? "Request failed");
  }
  return res.json();
}

export async function fetchWorkflowSchedules(
  token: string,
  workflowId: string
): Promise<{ schedules: WorkflowSchedule[] }> {
  const res = await fetch(`/api/v1/workflows/${workflowId}/schedules`, {
    headers: headers(token),
    cache: "no-store",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? "Request failed");
  }
  return res.json();
}

export async function createWorkflowSchedule(
  token: string,
  workflowId: string,
  payload: { cron_expression: string; enabled: boolean }
): Promise<WorkflowSchedule> {
  const res = await fetch(`/api/v1/workflows/${workflowId}/schedules`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail ?? "Request failed");
  }
  return data;
}

export async function updateWorkflowSchedule(
  token: string,
  scheduleId: string,
  payload: { cron_expression?: string; enabled?: boolean }
): Promise<WorkflowSchedule> {
  const res = await fetch(`/api/v1/workflows/schedules/${scheduleId}`, {
    method: "PATCH",
    headers: headers(token),
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail ?? "Request failed");
  }
  return data;
}

export async function promoteWorkflowVersion(
  token: string,
  workflowId: string,
  versionId: string,
  toEnvironment: string
): Promise<{ source_version_id: string; target_version_id: string; version: number; environment: string }> {
  const res = await fetch(`/api/v1/workflows/${workflowId}/versions/${versionId}/promote`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify({ to_environment: toEnvironment }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}
