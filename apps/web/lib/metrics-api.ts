/**
 * MT-10: Client helpers for metrics API (same-origin). Pass token from useAuth().
 */

import { getEnvironmentHeader } from "@/lib/environment";

const API = "/api/metrics";

export type Range = "7d" | "30d" | "90d";

export type MetricsOverview = {
  range: Range;
  workflows: {
    dry_runs_total: number;
    exec_runs_total: number;
    exec_success_rate: number;
    pending_approvals: number;
  };
  rag: {
    retrieval_requests_total: number;
    avg_latency_ms: number;
    p95_latency_ms: number;
    avg_result_count: number;
    insufficient_data?: boolean;
  };
  ingestion: {
    ingest_jobs_total: number;
    ingest_success_rate: number;
    chunks_embedded_total: number;
  };
  connectors: {
    slack_sent: number;
    email_sent: number;
    webhook_sent: number;
    send_failures_total: number;
  };
};

export type MetricsWorkflows = {
  range: Range;
  exec: {
    by_status: Record<string, number>;
    approval_funnel: { created: number; approved: number; rejected: number };
    avg_duration_ms: number;
    p95_duration_ms: number;
    step_failures_by_type: Record<string, number>;
  };
  dry_run: {
    total: number;
    rag_step_failure_rate: number;
  };
};

export type MetricsRag = {
  range: Range;
  retrieval: {
    total: number;
    avg_latency_ms: number;
    p95_latency_ms: number;
    avg_result_count: number;
    zero_result_rate: number;
    insufficient_data?: boolean;
  };
  ingestion: {
    jobs_total: number;
    by_status: Record<string, number>;
    avg_chunks_per_job: number;
    p95_chunks_per_job: number;
  };
};

export type MetricsIntegrations = {
  range: Range;
  slack: { sent: number; failed: number };
  email: { sent: number; failed: number };
  webhook: { sent: number; failed: number };
};

export type MetricsTimeseries = {
  range: Range;
  metric: string;
  points: Array<{ date: string; value: number }>;
};

function headers(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
    "X-Environment": getEnvironmentHeader(),
  };
}

export async function fetchMetricsOverview(token: string, range: Range): Promise<MetricsOverview> {
  const res = await fetch(`${API}/overview?range=${range}`, {
    headers: headers(token),
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data;
}

export async function fetchMetricsWorkflows(token: string, range: Range): Promise<MetricsWorkflows> {
  const res = await fetch(`${API}/workflows?range=${range}`, {
    headers: headers(token),
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data;
}

export async function fetchMetricsRag(token: string, range: Range): Promise<MetricsRag> {
  const res = await fetch(`${API}/rag?range=${range}`, {
    headers: headers(token),
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data;
}

export async function fetchMetricsIntegrations(token: string, range: Range): Promise<MetricsIntegrations> {
  const res = await fetch(`${API}/integrations?range=${range}`, {
    headers: headers(token),
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data;
}

export async function fetchMetricsTimeseries(
  token: string,
  range: Range,
  metric: string
): Promise<MetricsTimeseries> {
  const res = await fetch(`${API}/timeseries?range=${range}&metric=${metric}`, {
    headers: headers(token),
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data;
}
