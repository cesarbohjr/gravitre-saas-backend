"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getEnvironmentHeader } from "@/lib/environment";
import { useAuth } from "@/lib/use-auth";
import {
  fetchRuns,
  fetchWorkflows,
  type RunListItem,
  type WorkflowListItem,
} from "@/lib/workflows-api";

const STATUS_OPTIONS = [
  { value: "all", label: "All statuses" },
  { value: "running", label: "Running" },
  { value: "pending_approval", label: "Pending approval" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
];

const APPROVAL_OPTIONS = [
  { value: "all", label: "All approvals" },
  { value: "pending_approval", label: "Needs approval" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "none", label: "Not required" },
];

const TIME_RANGE_OPTIONS = [
  { value: "24h", label: "Last 24h" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
  { value: "all", label: "All time" },
];

function getRangeStart(range: string): number | null {
  const now = Date.now();
  switch (range) {
    case "24h":
      return now - 24 * 60 * 60 * 1000;
    case "7d":
      return now - 7 * 24 * 60 * 60 * 1000;
    case "30d":
      return now - 30 * 24 * 60 * 60 * 1000;
    case "90d":
      return now - 90 * 24 * 60 * 60 * 1000;
    default:
      return null;
  }
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString();
}

function formatDuration(start?: string | null, end?: string | null): string {
  if (!start) return "—";
  const startMs = new Date(start).getTime();
  if (Number.isNaN(startMs)) return "—";
  if (!end) return "In progress";
  const endMs = new Date(end).getTime();
  if (Number.isNaN(endMs)) return "—";
  const totalSeconds = Math.max(0, Math.floor((endMs - startMs) / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${remainingMinutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

function StatusBadge({ status }: { status?: string | null }) {
  const normalized = status ?? "unknown";
  const variant =
    normalized === "completed"
      ? "bg-success/15 text-success border-border"
      : normalized === "failed"
        ? "bg-destructive/15 text-destructive border-border"
        : normalized === "running"
          ? "bg-warning/15 text-warning border-border"
          : normalized === "pending_approval"
            ? "bg-warning/15 text-warning border-border"
            : "bg-muted text-muted-foreground border-border";
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${variant}`}>
      {normalized.replace("_", " ")}
    </span>
  );
}

function ApprovalBadge({ status }: { status?: string | null }) {
  if (!status) {
    return (
      <span className="inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium bg-muted text-muted-foreground border-border">
        Not required
      </span>
    );
  }
  const variant =
    status === "approved"
      ? "bg-success/15 text-success border-border"
      : status === "rejected"
        ? "bg-destructive/15 text-destructive border-border"
        : "bg-warning/15 text-warning border-border";
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${variant}`}>
      {status.replace("_", " ")}
    </span>
  );
}

export default function RunsPage() {
  const auth = useAuth();
  const environment = getEnvironmentHeader();
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [approvalFilter, setApprovalFilter] = useState("all");
  const [workflowFilter, setWorkflowFilter] = useState("all");
  const [timeRange, setTimeRange] = useState("30d");
  const [search, setSearch] = useState("");

  const loadRuns = useCallback(() => {
    if (auth.status !== "authenticated" || auth.orgId == null) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    Promise.all([fetchRuns(auth.token, { limit: 200 }), fetchWorkflows(auth.token)])
      .then(([runsData, workflowsData]) => {
        setRuns(runsData.runs);
        setWorkflows(workflowsData.workflows);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load runs."))
      .finally(() => setLoading(false));
  }, [auth.status, auth.token, auth.orgId]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  const filteredRuns = useMemo(() => {
    let filtered = runs;
    if (statusFilter !== "all") {
      filtered = filtered.filter((run) => run.status === statusFilter);
    }
    if (approvalFilter !== "all") {
      filtered =
        approvalFilter === "none"
          ? filtered.filter((run) => !run.approval_status)
          : filtered.filter((run) => run.approval_status === approvalFilter);
    }
    if (workflowFilter !== "all") {
      filtered = filtered.filter((run) => run.workflow_id === workflowFilter);
    }
    if (timeRange !== "all") {
      const startAt = getRangeStart(timeRange);
      if (startAt != null) {
        filtered = filtered.filter((run) => {
          if (!run.created_at) return false;
          const createdAt = new Date(run.created_at).getTime();
          return !Number.isNaN(createdAt) && createdAt >= startAt;
        });
      }
    }
    const trimmedSearch = search.trim().toLowerCase();
    if (trimmedSearch) {
      filtered = filtered.filter((run) => {
        const idMatch = run.id?.toLowerCase().includes(trimmedSearch);
        const nameMatch = run.workflow_name?.toLowerCase().includes(trimmedSearch);
        return Boolean(idMatch || nameMatch);
      });
    }
    return filtered;
  }, [runs, statusFilter, approvalFilter, workflowFilter, timeRange, search]);

  const activeCount = filteredRuns.filter((run) => run.status === "running").length;
  const needsApprovalCount = filteredRuns.filter(
    (run) => run.status === "pending_approval" || run.approval_status === "pending_approval"
  ).length;
  const failedCount = filteredRuns.filter((run) => run.status === "failed").length;

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Runs</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to view runs."}
          </p>
        </CardContent>
      </Card>
    );
  }

  if (auth.orgId == null) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Runs</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Onboarding pending. Contact admin for org access to view runs.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">Runs</h1>
        <p className="text-sm text-muted-foreground">
          Environment: <span className="font-medium text-foreground">{environment}</span>
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Active</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between">
            <div className="text-2xl font-semibold text-foreground">{activeCount}</div>
            <span className="h-2 w-2 rounded-full bg-success" />
          </CardContent>
        </Card>
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Needs approval</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between">
            <div className="text-2xl font-semibold text-foreground">{needsApprovalCount}</div>
            <span className="h-2 w-2 rounded-full bg-warning" />
          </CardContent>
        </Card>
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Failed</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between">
            <div className="text-2xl font-semibold text-foreground">{failedCount}</div>
            <span className="h-2 w-2 rounded-full bg-destructive" />
          </CardContent>
        </Card>
      </div>

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Run history</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="run-status">
                Status
              </label>
              <select
                id="run-status"
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="run-approval">
                Approval status
              </label>
              <select
                id="run-approval"
                value={approvalFilter}
                onChange={(event) => setApprovalFilter(event.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {APPROVAL_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="run-workflow">
                Workflow
              </label>
              <select
                id="run-workflow"
                value={workflowFilter}
                onChange={(event) => setWorkflowFilter(event.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="all">All workflows</option>
                {workflows.map((wf) => (
                  <option key={wf.id} value={wf.id}>
                    {wf.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="run-range">
                Time range
              </label>
              <select
                id="run-range"
                value={timeRange}
                onChange={(event) => setTimeRange(event.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {TIME_RANGE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1 xl:col-span-1 md:col-span-2">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="run-search">
                Search
              </label>
              <input
                id="run-search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Run ID or workflow"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
          </div>

          {error && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-destructive/5 px-3 py-2">
              <p className="text-sm text-destructive">{error}</p>
              <Button variant="secondary" size="sm" onClick={loadRuns}>
                Retry
              </Button>
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full min-w-[920px] text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-2 pr-4 font-medium text-foreground">Run</th>
                  <th className="py-2 pr-4 font-medium text-foreground">Workflow</th>
                  <th className="py-2 pr-4 font-medium text-foreground">Status</th>
                  <th className="py-2 pr-4 font-medium text-foreground">Approval</th>
                  <th className="py-2 pr-4 font-medium text-foreground">Environment</th>
                  <th className="py-2 pr-4 font-medium text-foreground">Started</th>
                  <th className="py-2 font-medium text-foreground">Duration</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  Array.from({ length: 5 }).map((_, idx) => (
                    <tr key={`skeleton-${idx}`} className="border-b border-border animate-pulse">
                      <td className="py-3 pr-4">
                        <div className="h-4 w-32 rounded bg-muted" />
                      </td>
                      <td className="py-3 pr-4">
                        <div className="h-4 w-40 rounded bg-muted" />
                      </td>
                      <td className="py-3 pr-4">
                        <div className="h-4 w-20 rounded bg-muted" />
                      </td>
                      <td className="py-3 pr-4">
                        <div className="h-4 w-24 rounded bg-muted" />
                      </td>
                      <td className="py-3 pr-4">
                        <div className="h-4 w-20 rounded bg-muted" />
                      </td>
                      <td className="py-3 pr-4">
                        <div className="h-4 w-28 rounded bg-muted" />
                      </td>
                      <td className="py-3">
                        <div className="h-4 w-20 rounded bg-muted" />
                      </td>
                    </tr>
                  ))
                ) : filteredRuns.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-6 text-sm text-muted-foreground">
                      No runs yet.
                    </td>
                  </tr>
                ) : (
                  filteredRuns.map((run) => (
                    <tr key={run.id} className="border-b border-border hover:bg-muted/50">
                      <td className="py-3 pr-4">
                        <Link
                          href={`/runs/${run.id}`}
                          className="text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                        >
                          {run.id.slice(0, 8)}…
                        </Link>
                      </td>
                      <td className="py-3 pr-4">
                        {run.workflow_id ? (
                          <Link
                            href={`/workflows/${run.workflow_id}`}
                            className="text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                          >
                            {run.workflow_name || "Workflow"}
                          </Link>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="py-3 pr-4">
                        <StatusBadge status={run.status} />
                      </td>
                      <td className="py-3 pr-4">
                        <ApprovalBadge status={run.approval_status} />
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground">
                        {run.environment || environment}
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground">
                        {formatDate(run.created_at)}
                      </td>
                      <td className="py-3 text-muted-foreground">
                        {formatDuration(run.created_at, run.completed_at)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="text-sm text-muted-foreground">
        Need to manage approvals?{" "}
        <Link href="/approvals" className="text-primary hover:underline">
          Go to approvals
        </Link>
        .
      </div>
    </div>
  );
}
