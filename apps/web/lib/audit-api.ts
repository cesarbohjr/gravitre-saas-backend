/**
 * FE-11: Audit API (same-origin). Pass token from useAuth().
 */

import { getEnvironmentHeader } from "@/lib/environment";

export type AuditItem = {
  id: string;
  action: string;
  actor_id: string;
  resource_type: string;
  resource_id: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
};

export type AuditResponse = {
  items: AuditItem[];
  next_cursor: string | null;
};

export type FetchAuditOptions = {
  limit?: number;
  cursor?: string | null;
  action_prefix?: string | null;
};

function headers(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
    "X-Environment": getEnvironmentHeader(),
  };
}

export async function fetchAuditEvents(
  token: string,
  resourceType: string,
  resourceId: string,
  options: FetchAuditOptions = {}
): Promise<AuditResponse> {
  const params = new URLSearchParams();
  params.set("resource_type", resourceType);
  params.set("resource_id", resourceId);
  if (options.limit != null) params.set("limit", String(options.limit));
  if (options.cursor) params.set("cursor", options.cursor);
  if (options.action_prefix) params.set("action_prefix", options.action_prefix);

  const res = await fetch(`/api/audit?${params.toString()}`, {
    headers: headers(token),
    cache: "no-store",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(
      res.status === 401
        ? "Unauthorized"
        : res.status === 503
          ? "Backend unavailable"
          : (data.detail as string) ?? "Request failed"
    );
  }
  return res.json();
}

export type FetchAuditLogOptions = {
  limit?: number;
  cursor?: string | null;
  action?: string | null;
  action_prefix?: string | null;
  actor_id?: string | null;
  resource_type?: string | null;
  start_at?: string | null;
  end_at?: string | null;
};

export async function fetchAuditLog(
  token: string,
  options: FetchAuditLogOptions = {}
): Promise<AuditResponse> {
  const params = new URLSearchParams();
  if (options.limit != null) params.set("limit", String(options.limit));
  if (options.cursor) params.set("cursor", options.cursor);
  if (options.action) params.set("action", options.action);
  if (options.action_prefix) params.set("action_prefix", options.action_prefix);
  if (options.actor_id) params.set("actor_id", options.actor_id);
  if (options.resource_type) params.set("resource_type", options.resource_type);
  if (options.start_at) params.set("start_at", options.start_at);
  if (options.end_at) params.set("end_at", options.end_at);

  const res = await fetch(`/api/audit?${params.toString()}`, {
    headers: headers(token),
    cache: "no-store",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(
      res.status === 401
        ? "Unauthorized"
        : res.status === 503
          ? "Backend unavailable"
          : (data.detail as string) ?? "Request failed"
    );
  }
  return res.json();
}

/** Human-readable labels for workflow.dry_run.* actions */
export const AUDIT_ACTION_LABELS: Record<string, string> = {
  "workflow.dry_run.started": "Dry run started",
  "workflow.dry_run.step_completed": "Step completed",
  "workflow.dry_run.step_failed": "Step failed",
  "workflow.dry_run.completed": "Dry run completed",
};

export function getActionLabel(action: string): string {
  return AUDIT_ACTION_LABELS[action] ?? action;
}
