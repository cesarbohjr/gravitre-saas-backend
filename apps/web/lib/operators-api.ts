import { getEnvironmentHeader } from "@/lib/environment";

const API = "/api/v1/operators";

export type OperatorStatus = "draft" | "active" | "inactive";
export type SessionStatus =
  | "idle"
  | "planning"
  | "review"
  | "awaiting_approval"
  | "executing"
  | "paused"
  | "completed"
  | "failed";

export type OperatorConnector = {
  id: string;
  type: string;
  status: string;
  environment: string;
  updated_at?: string | null;
  config: Record<string, unknown>;
};

export type OperatorSummary = {
  id: string;
  name: string;
  description?: string | null;
  status: OperatorStatus;
  allowed_environments: string[];
  requires_admin: boolean;
  requires_approval: boolean;
  approval_roles: string[];
  active_version?: OperatorVersionSummary | null;
};

export type OperatorDetail = OperatorSummary & {
  system_prompt?: string | null;
  connectors: OperatorConnector[];
  created_at?: string | null;
  updated_at?: string | null;
};

export type OperatorVersionSummary = {
  id: string;
  operator_id: string;
  environment: string;
  version: number;
  name: string;
  description?: string | null;
  created_at?: string | null;
};

export type OperatorLinkSummary = {
  id: string;
  from_operator_id: string;
  to_operator_id: string;
  environment: string;
  link_type: string;
  task?: string | null;
  notes?: string | null;
  created_by?: string | null;
  created_at?: string | null;
};

export type OperatorSessionSummary = {
  id: string;
  operator_id: string;
  operator_version_id?: string | null;
  title: string;
  status: SessionStatus;
  environment: string;
  current_task?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type OperatorActionPlan = {
  plan_id: string;
  title: string;
  summary: string;
  steps: Array<Record<string, unknown>>;
  guardrails: Record<string, unknown>;
  status: string;
  operator_version_id?: string | null;
  created_at?: string | null;
};

export type OperatorAction = {
  id: string;
  step_id: string;
  action_type: string;
  status: string;
  workflow_run_id?: string | null;
  created_at?: string | null;
};

export type OperatorSessionDetail = {
  session: OperatorSessionSummary;
  operator: OperatorSummary;
  latest_plan?: OperatorActionPlan | null;
  actions: OperatorAction[];
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

export async function fetchOperators(
  token: string,
  includeInactive = false
): Promise<{ operators: OperatorSummary[] }> {
  const url = includeInactive ? `${API}?include_inactive=true` : API;
  const res = await fetch(url, { headers: headers(token), cache: "no-store" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function fetchOperator(token: string, id: string): Promise<OperatorDetail> {
  const res = await fetch(`${API}/${id}`, { headers: headers(token), cache: "no-store" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function createOperator(
  token: string,
  payload: {
    name: string;
    description?: string | null;
    status?: OperatorStatus;
    system_prompt?: string | null;
    allowed_environments?: string[] | null;
    requires_admin?: boolean;
    requires_approval?: boolean;
    approval_roles?: string[];
    connector_ids?: string[];
  }
): Promise<OperatorDetail> {
  const res = await fetch(API, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function fetchOperatorLinks(
  token: string,
  operatorId: string,
  direction: "outgoing" | "incoming" | "all" = "outgoing"
): Promise<{ links: OperatorLinkSummary[] }> {
  const res = await fetch(`${API}/${operatorId}/links?direction=${direction}`, {
    headers: headers(token),
    cache: "no-store",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function createOperatorLink(
  token: string,
  operatorId: string,
  payload: { to_operator_id: string; link_type?: string; task?: string | null; notes?: string | null }
): Promise<OperatorLinkSummary> {
  const res = await fetch(`${API}/${operatorId}/links`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function deleteOperatorLink(
  token: string,
  operatorId: string,
  linkId: string
): Promise<void> {
  const res = await fetch(`${API}/${operatorId}/links/${linkId}`, {
    method: "DELETE",
    headers: headers(token),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
}

export async function updateOperator(
  token: string,
  id: string,
  payload: {
    name?: string | null;
    description?: string | null;
    status?: OperatorStatus | null;
    system_prompt?: string | null;
    allowed_environments?: string[] | null;
    requires_admin?: boolean | null;
    requires_approval?: boolean | null;
    approval_roles?: string[] | null;
    connector_ids?: string[] | null;
  }
): Promise<OperatorDetail> {
  const res = await fetch(`${API}/${id}`, {
    method: "PATCH",
    headers: headers(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function fetchOperatorSessions(
  token: string,
  operatorId: string,
  scope: "mine" | "all" = "mine"
): Promise<{ sessions: OperatorSessionSummary[] }> {
  const url = scope === "all" ? `${API}/${operatorId}/sessions?scope=all` : `${API}/${operatorId}/sessions`;
  const res = await fetch(url, { headers: headers(token), cache: "no-store" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function createOperatorSession(
  token: string,
  operatorId: string,
  payload: { title: string; current_task?: string | null }
): Promise<OperatorSessionSummary> {
  const res = await fetch(`${API}/${operatorId}/sessions`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function fetchOperatorSessionDetail(
  token: string,
  sessionId: string
): Promise<OperatorSessionDetail> {
  const res = await fetch(`${API}/sessions/${sessionId}`, {
    headers: headers(token),
    cache: "no-store",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function createOperatorActionPlan(
  token: string,
  operatorId: string,
  payload: {
    session_id: string;
    primary_context: { type: "run" | "workflow" | "connector" | "source"; id: string };
    related_contexts?: Array<{ type: "run" | "workflow" | "connector" | "source"; id: string }>;
    operator_goal?: string | null;
    prompt?: string | null;
  }
): Promise<OperatorActionPlan> {
  const res = await fetch(`${API}/${operatorId}/action-plans`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function runOperatorAction(
  token: string,
  operatorId: string,
  payload: {
    session_id: string;
    plan_id: string;
    step_id: string;
    confirm: boolean;
    parameters?: Record<string, unknown> | null;
  }
): Promise<{ action_id: string; workflow_run_id?: string | null; status: string; approval_required?: boolean; approval_status?: string | null }> {
  const res = await fetch(`${API}/${operatorId}/run`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function fetchOperatorVersions(
  token: string,
  operatorId: string
): Promise<{ versions: OperatorVersionSummary[] }> {
  const res = await fetch(`${API}/${operatorId}/versions`, {
    headers: headers(token),
    cache: "no-store",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function createOperatorVersion(
  token: string,
  operatorId: string
): Promise<OperatorVersionSummary> {
  const res = await fetch(`${API}/${operatorId}/versions`, {
    method: "POST",
    headers: headers(token),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function activateOperatorVersion(
  token: string,
  operatorId: string,
  versionId: string
): Promise<{ active_version_id: string; version: number }> {
  const res = await fetch(`${API}/${operatorId}/versions/${versionId}/activate`, {
    method: "POST",
    headers: headers(token),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}
