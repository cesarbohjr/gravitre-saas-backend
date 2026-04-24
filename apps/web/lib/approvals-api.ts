import { getEnvironmentHeader } from "@/lib/environment";

const API = "/api/v1";

export type PendingApprovalItem = {
  run_id: string;
  workflow_id: string | null;
  workflow_name: string | null;
  created_at: string;
  required_approvals: number;
  approvals_received: number;
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

export async function fetchPendingApprovals(
  token: string
): Promise<{ items: PendingApprovalItem[] }> {
  const res = await fetch(`${API}/approvals/pending`, {
    headers: headers(token),
    cache: "no-store",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function approveRun(token: string, runId: string, comment?: string): Promise<unknown> {
  const res = await fetch(`${API}/workflows/runs/${runId}/approve`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify({ comment: comment || null }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function rejectRun(token: string, runId: string, comment?: string): Promise<unknown> {
  const res = await fetch(`${API}/workflows/runs/${runId}/reject`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify({ comment: comment || null }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}
