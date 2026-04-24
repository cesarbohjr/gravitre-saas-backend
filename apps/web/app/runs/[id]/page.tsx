"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import { fetchRun, rollbackRun, type RunDetail, type StepOut } from "@/lib/workflows-api";
import { ApiError, approveRun, rejectRun } from "@/lib/approvals-api";
import {
  fetchAuditEvents,
  getActionLabel,
  type AuditItem,
} from "@/lib/audit-api";
import { getEnvironmentHeader } from "@/lib/environment";

const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function isValidUUID(s: string): boolean {
  return UUID_REGEX.test(s);
}

function AuditTimelineItem({
  item,
  variant,
}: {
  item: AuditItem;
  variant: "started" | "completed" | "failed" | "step" | "default";
}) {
  const meta = item.metadata ?? {};
  const stepIndex = meta.step_index;
  const stepId = meta.step_id as string | undefined;

  const variantClass =
    variant === "started"
      ? "border-l-4 border-l-primary"
      : variant === "completed"
        ? "border-l-4 border-l-success"
        : variant === "failed"
          ? "border-l-4 border-l-destructive"
          : variant === "step"
            ? "border-l-4 border-l-warning"
            : "border-l-4 border-l-border";

  return (
    <div
      className={`border-l-4 pl-3 py-2 ${variantClass} border-border rounded-r`}
    >
      <p className="text-sm font-medium text-foreground">
        {getActionLabel(item.action)}
      </p>
      <p className="text-xs text-muted-foreground mt-0.5">
        {new Date(item.created_at).toLocaleString()}
        {(stepIndex != null || stepId) && (
          <span className="ml-2">
            {stepIndex != null && `step ${Number(stepIndex) + 1}`}
            {stepId && ` · ${stepId}`}
          </span>
        )}
      </p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const variant =
    status === "completed"
      ? "bg-success/15 text-success border-border"
      : status === "failed"
        ? "bg-destructive/15 text-destructive border-border"
        : status === "running"
          ? "bg-warning/15 text-warning border-border"
          : "bg-muted text-muted-foreground border-border";
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${variant}`}
    >
      {status}
    </span>
  );
}

function StepDetail({ step }: { step: StepOut }) {
  const [open, setOpen] = useState(false);
  const hasOutput = step.output_snapshot && Object.keys(step.output_snapshot).length > 0;
  const hasError = step.error_code || step.error_message;

  return (
    <Card className="border-border bg-[hsl(var(--surface))]">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">
            {step.step_name}
            <span className="ml-2 font-mono text-xs text-muted-foreground">
              {step.step_id}
            </span>
          </CardTitle>
          <StatusBadge status={step.status} />
        </div>
        <p className="text-xs text-muted-foreground">
          {step.step_type}
          {step.is_retryable && " · retryable"}
        </p>
      </CardHeader>
      <CardContent className="space-y-2">
        {hasError && (
          <div className="rounded-md border border-border bg-destructive/5 p-2 text-sm">
            {step.error_code && (
              <p className="font-medium text-destructive">{step.error_code}</p>
            )}
            {step.error_message && (
              <p className="text-muted-foreground">{step.error_message}</p>
            )}
          </div>
        )}
        {hasOutput && (
          <div>
            <button
              type="button"
              onClick={() => setOpen(!open)}
              className="text-sm font-medium text-foreground hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
              aria-expanded={open}
            >
              {open ? "Hide" : "Show"} output
            </button>
            {open && (
              <pre className="mt-2 overflow-auto rounded-md border border-border bg-background p-3 text-xs font-mono text-foreground max-h-64">
                {JSON.stringify(step.output_snapshot, null, 2)}
              </pre>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function RunDetailPage() {
  const params = useParams();
  const runId = params.id as string;
  const auth = useAuth();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedStep, setSelectedStep] = useState<StepOut | null>(null);
  const [auditItems, setAuditItems] = useState<AuditItem[]>([]);
  const [auditNextCursor, setAuditNextCursor] = useState<string | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [loadMoreLoading, setLoadMoreLoading] = useState(false);
  const [approvalActionError, setApprovalActionError] = useState<string | null>(null);
  const [approvalActionLoading, setApprovalActionLoading] = useState<string | null>(null);
  const [approvalActionAllowed, setApprovalActionAllowed] = useState(true);
  const [approvalConfirm, setApprovalConfirm] = useState<"approve" | "reject" | null>(null);
  const [rollbackLoading, setRollbackLoading] = useState(false);
  const [rollbackError, setRollbackError] = useState<string | null>(null);
  const [rollbackConfirm, setRollbackConfirm] = useState(false);
  const environment = getEnvironmentHeader();
  const isAdmin = auth.status === "authenticated" && auth.role === "admin";
  const canManageApproval = isAdmin && approvalActionAllowed;
  const canRollback = isAdmin;

  const fetchAudit = useCallback(
    (cursor: string | null = null, append = false) => {
      if (auth.status !== "authenticated" || !runId || !isValidUUID(runId))
        return;
      const setLoadingState = append ? setLoadMoreLoading : setAuditLoading;
      if (!append) setAuditError(null);
      setLoadingState(true);
      fetchAuditEvents(auth.token, "workflow_run", runId, {
        limit: 50,
        cursor,
        action_prefix: "workflow.dry_run.",
      })
        .then((res) => {
          if (append) {
            setAuditItems((prev) => [...prev, ...res.items]);
          } else {
            setAuditItems(res.items);
          }
          setAuditNextCursor(res.next_cursor ?? null);
        })
        .catch((e) => setAuditError(e.message ?? "Failed to load audit"))
        .finally(() => setLoadingState(false));
    },
    [auth.status, auth.token, runId]
  );

  useEffect(() => {
    if (auth.status !== "authenticated") {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchRun(auth.token, runId)
      .then((data) => {
        if (!cancelled) {
          setRun(data);
          if (data.steps?.length) setSelectedStep(data.steps[0]);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e.message ?? "Failed to load");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [runId, auth.status, auth.token]);

  useEffect(() => {
    if (auth.status === "authenticated" && isValidUUID(runId)) {
      fetchAudit(null, false);
    }
  }, [runId, auth.status, fetchAudit]);

  const handleApprove = () => {
    if (!run || auth.status !== "authenticated" || !canManageApproval) return;
    setApprovalConfirm("approve");
  };

  const handleReject = () => {
    if (!run || auth.status !== "authenticated" || !canManageApproval) return;
    setApprovalConfirm("reject");
  };

  const handleConfirmApproval = async () => {
    if (!run || auth.status !== "authenticated" || !canManageApproval || !approvalConfirm) return;
    setApprovalActionError(null);
    setApprovalActionLoading(approvalConfirm);
    try {
      if (approvalConfirm === "approve") {
        await approveRun(auth.token, run.id);
      } else {
        await rejectRun(auth.token, run.id);
      }
      const updated = await fetchRun(auth.token, run.id);
      setRun(updated);
      setApprovalConfirm(null);
    } catch (e) {
      const fallback = approvalConfirm === "approve" ? "Approval failed" : "Rejection failed";
      const message = e instanceof Error ? e.message : fallback;
      setApprovalActionError(message);
      if (e instanceof ApiError && e.status === 403) {
        setApprovalActionAllowed(false);
      }
    } finally {
      setApprovalActionLoading(null);
    }
  };

  const handleRollback = () => {
    if (!run || auth.status !== "authenticated" || !canRollback) return;
    setRollbackConfirm(true);
  };

  const handleCancelRollback = () => {
    setRollbackConfirm(false);
  };

  const handleConfirmRollback = async () => {
    if (!run || auth.status !== "authenticated" || !canRollback) return;
    setRollbackError(null);
    setRollbackLoading(true);
    try {
      await rollbackRun(auth.token, run.id);
      const updated = await fetchRun(auth.token, run.id);
      setRun(updated);
      setRollbackConfirm(false);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Rollback failed";
      setRollbackError(message);
    } finally {
      setRollbackLoading(false);
    }
  };

  const handleCancelConfirm = () => setApprovalConfirm(null);

  if (!isValidUUID(runId)) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-destructive">Invalid run ID.</p>
          <Link
            href="/workflows"
            className="mt-2 inline-block text-sm text-primary hover:underline"
          >
            Back to workflows
          </Link>
        </CardContent>
      </Card>
    );
  }

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
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
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">
            Onboarding pending. Contact admin for org access.
          </p>
        </CardContent>
      </Card>
    );
  }

  const approvalPending =
    run?.approval_required && run.approval_status === "pending_approval";

  if (error) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-destructive">{error}</p>
          <Link href="/workflows" className="mt-2 inline-block text-sm text-primary hover:underline">
            Back to workflows
          </Link>
        </CardContent>
      </Card>
    );
  }

  if (loading || !run) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">Loading run…</p>
        </CardContent>
      </Card>
    );
  }

  const steps = run.steps ?? [];

  return (
    <div className="space-y-6">
      {approvalPending && (
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardHeader>
            <CardTitle className="text-lg">Pending approval</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Environment: <span className="font-medium text-foreground">{environment}</span>
            </p>
            <p className="text-sm text-muted-foreground">
              Approvals required: {run?.required_approvals ?? 0} · Received:{" "}
              {run?.approvals_received ?? 0}
            </p>
            {approvalActionError && (
              <p className="text-sm text-destructive">{approvalActionError}</p>
            )}
            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                size="sm"
                onClick={handleApprove}
                disabled={!canManageApproval || approvalActionLoading === "approve"}
              >
                Approve
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleReject}
                disabled={!canManageApproval || approvalActionLoading === "reject"}
              >
                Reject
              </Button>
            </div>
            {approvalConfirm && (
              <div className="rounded-md border border-border bg-muted/40 p-3 space-y-2">
                <p className="text-sm text-muted-foreground">
                  Confirm {approvalConfirm} for run {run.id.slice(0, 8)}… in{" "}
                  <span className="font-medium text-foreground">{environment}</span>
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleConfirmApproval}
                    disabled={approvalActionLoading === approvalConfirm}
                  >
                    Confirm {approvalConfirm}
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleCancelConfirm}
                    disabled={approvalActionLoading === approvalConfirm}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              Admin permission required to approve or reject.
            </p>
            {!isAdmin && (
              <p className="text-xs text-muted-foreground">You have read-only access.</p>
            )}
          </CardContent>
        </Card>
      )}
      <div className="flex items-center gap-4">
        <Link
          href="/workflows"
          className="text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
        >
          ← Workflows
        </Link>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          Run {runId.slice(0, 8)}…
        </h1>
        <StatusBadge status={run.status} />
      </div>
      <p className="text-sm text-muted-foreground">
        Environment: <span className="font-medium text-foreground">{environment}</span>
      </p>

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Run info</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-1">
          <p>Type: {run.run_type}</p>
          <p>Created: {new Date(run.created_at).toLocaleString()}</p>
          {run.completed_at && (
            <p>Completed: {new Date(run.completed_at).toLocaleString()}</p>
          )}
          {run.error_message && (
            <p className="text-destructive">{run.error_message}</p>
          )}
        </CardContent>
      </Card>

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Execution flow</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {steps.length === 0 ? (
            <p className="text-sm text-muted-foreground">No steps recorded for this run.</p>
          ) : (
            <div className="space-y-2">
              {steps.map((step, index) => (
                <div
                  key={step.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-muted/30 px-3 py-2"
                >
                  <div className="text-sm text-foreground">
                    {index + 1}. {step.step_name}
                    <span className="ml-2 text-xs text-muted-foreground">{step.step_type}</span>
                  </div>
                  <StatusBadge status={step.status} />
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Rollback</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Trigger a rollback run using the current workflow definition. Rollback behavior depends on workflow logic.
          </p>
          {rollbackError && <p className="text-sm text-destructive">{rollbackError}</p>}
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleRollback}
              disabled={!canRollback || rollbackLoading}
            >
              Request rollback
            </Button>
            {!canRollback && (
              <span className="text-xs text-muted-foreground">Admin permission required.</span>
            )}
          </div>
          {rollbackConfirm && (
            <div className="rounded-md border border-border bg-muted/40 p-3 space-y-2">
              <p className="text-sm text-muted-foreground">
                Confirm rollback for run {run.id.slice(0, 8)}… in{" "}
                <span className="font-medium text-foreground">{environment}</span>
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleConfirmRollback}
                  disabled={rollbackLoading}
                >
                  Confirm rollback
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleCancelRollback}
                  disabled={rollbackLoading}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 md:grid-cols-[1fr,1fr]">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-foreground mb-3">
            Steps
          </h2>
          <div className="rounded-md border border-border overflow-hidden">
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="py-2 px-3 font-medium text-foreground">#</th>
                  <th className="py-2 px-3 font-medium text-foreground">Name</th>
                  <th className="py-2 px-3 font-medium text-foreground">Type</th>
                  <th className="py-2 px-3 font-medium text-foreground">Status</th>
                </tr>
              </thead>
              <tbody>
                {steps.map((s) => (
                  <tr
                    key={s.id}
                    className={`border-b border-border cursor-pointer hover:bg-muted/50 ${
                      selectedStep?.id === s.id ? "bg-muted/50" : ""
                    }`}
                    onClick={() => setSelectedStep(s)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelectedStep(s);
                      }
                    }}
                    tabIndex={0}
                    role="button"
                  >
                    <td className="py-2 px-3">{s.step_index + 1}</td>
                    <td className="py-2 px-3">{s.step_name}</td>
                    <td className="py-2 px-3 text-muted-foreground">
                      {s.step_type}
                    </td>
                    <td className="py-2 px-3">
                      <StatusBadge status={s.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-foreground mb-3">
            Step detail
          </h2>
          {selectedStep ? (
            <StepDetail step={selectedStep} />
          ) : (
            <p className="text-sm text-muted-foreground">
              Select a step from the table.
            </p>
          )}
        </div>
      </div>

      <section aria-labelledby="audit-heading" className="mt-8">
        <h2
          id="audit-heading"
          className="text-xl font-semibold tracking-tight text-foreground mb-3"
        >
          Audit
        </h2>
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardContent className="pt-6">
            {auditLoading ? (
              <p className="text-sm text-muted-foreground">Loading audit…</p>
            ) : auditError ? (
              <p className="text-sm text-destructive">{auditError}</p>
            ) : auditItems.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No audit events available.
              </p>
            ) : (
              <div className="space-y-2">
                {auditItems.map((item) => {
                  let variant: "started" | "completed" | "failed" | "step" | "default" =
                    "default";
                  if (item.action.includes("started")) variant = "started";
                  else if (item.action.includes("completed"))
                    variant = "completed";
                  else if (item.action.includes("failed")) variant = "failed";
                  else if (item.action.includes("step")) variant = "step";
                  return (
                    <AuditTimelineItem key={item.id} item={item} variant={variant} />
                  );
                })}
                {auditNextCursor && (
                  <div className="pt-4">
                    <Button
                      variant="secondary"
                      size="md"
                      onClick={() => fetchAudit(auditNextCursor, true)}
                      disabled={loadMoreLoading}
                      aria-busy={loadMoreLoading}
                    >
                      {loadMoreLoading ? "Loading…" : "Load more"}
                    </Button>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
