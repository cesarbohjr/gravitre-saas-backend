"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import {
  ApiError,
  fetchPendingApprovals,
  approveRun,
  rejectRun,
  type PendingApprovalItem,
} from "@/lib/approvals-api";
import { getEnvironmentHeader } from "@/lib/environment";

export default function ApprovalsPage() {
  const auth = useAuth();
  const [items, setItems] = useState<PendingApprovalItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionAllowed, setActionAllowed] = useState(true);
  const [confirmAction, setConfirmAction] = useState<{
    runId: string;
    action: "approve" | "reject";
  } | null>(null);
  const environment = getEnvironmentHeader();
  const isAdmin = auth.status === "authenticated" && auth.role === "admin";
  const canManage = isAdmin && actionAllowed;

  const load = () => {
    if (auth.status !== "authenticated" || auth.orgId == null) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    setActionAllowed(true);
    fetchPendingApprovals(auth.token)
      .then((data) => setItems(data.items))
      .catch((e) => setError(e.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [auth.status, auth.token, auth.orgId]);

  const handleApprove = (runId: string) => {
    if (auth.status !== "authenticated" || !canManage) return;
    setConfirmAction({ runId, action: "approve" });
  };

  const handleReject = (runId: string) => {
    if (auth.status !== "authenticated" || !canManage) return;
    setConfirmAction({ runId, action: "reject" });
  };

  const handleConfirmAction = async () => {
    if (!confirmAction || auth.status !== "authenticated" || !canManage) return;
    const { runId, action } = confirmAction;
    setActionError(null);
    setActionLoading(runId);
    try {
      if (action === "approve") {
        await approveRun(auth.token, runId);
      } else {
        await rejectRun(auth.token, runId);
      }
      load();
      setConfirmAction(null);
    } catch (e) {
      const fallback = action === "approve" ? "Approval failed" : "Rejection failed";
      const message = e instanceof Error ? e.message : fallback;
      setActionError(message);
      if (e instanceof ApiError && e.status === 403) {
        setActionAllowed(false);
      }
    } finally {
      setActionLoading(null);
    }
  };

  const confirmItem = confirmAction
    ? items.find((item) => item.run_id === confirmAction.runId)
    : null;

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Approvals</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to view approvals."}
          </p>
        </CardContent>
      </Card>
    );
  }

  if (auth.orgId == null) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Approvals</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Onboarding pending. Contact admin for org access.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Approvals</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">
            Approvals
          </h1>
          <p className="text-sm text-muted-foreground">
            Environment: <span className="font-medium text-foreground">{environment}</span>
          </p>
        </div>
      </div>

      {actionError && (
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">{actionError}</p>
          </CardContent>
        </Card>
      )}
      {confirmAction && (
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardHeader>
            <CardTitle className="text-lg">
              Confirm {confirmAction.action === "approve" ? "approval" : "rejection"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Environment: <span className="font-medium text-foreground">{environment}</span>
            </p>
            <p className="text-sm text-muted-foreground">
              Run {confirmAction.runId.slice(0, 8)}… ·{" "}
              {confirmItem?.workflow_name ?? confirmItem?.workflow_id ?? "Workflow"}
            </p>
            <p className="text-sm text-muted-foreground">
              Approvals required: {confirmItem?.required_approvals ?? 0} · Received:{" "}
              {confirmItem?.approvals_received ?? 0}
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                size="sm"
                onClick={handleConfirmAction}
                disabled={actionLoading === confirmAction.runId}
              >
                Confirm {confirmAction.action}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setConfirmAction(null)}
                disabled={actionLoading === confirmAction.runId}
              >
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Pending approvals</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-muted-foreground">No pending approvals.</p>
          ) : (
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-2 pr-4 font-medium text-foreground">Workflow</th>
                  <th className="py-2 pr-4 font-medium text-foreground">Gate</th>
                  <th className="py-2 pr-4 font-medium text-foreground">Required</th>
                  <th className="py-2 pr-4 font-medium text-foreground">Received</th>
                  <th className="py-2 pr-4 font-medium text-foreground">Created</th>
                  <th className="py-2 font-medium text-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.run_id} className="border-b border-border">
                    <td className="py-3 pr-4">
                      <Link
                        href={`/runs/${item.run_id}`}
                        className="text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                      >
                        {item.workflow_name ?? item.workflow_id ?? "Workflow"}
                      </Link>
                    </td>
                    <td className="py-3 pr-4 text-muted-foreground">Approval gate</td>
                    <td className="py-3 pr-4 text-muted-foreground">
                      {item.required_approvals}
                    </td>
                    <td className="py-3 pr-4 text-muted-foreground">
                      {item.approvals_received}
                    </td>
                    <td className="py-3 pr-4 text-muted-foreground">
                      {item.created_at ? new Date(item.created_at).toLocaleString() : "—"}
                    </td>
                    <td className="py-3">
                      <div className="flex items-center gap-2">
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => handleApprove(item.run_id)}
                          disabled={!canManage || actionLoading === item.run_id}
                        >
                          Approve
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleReject(item.run_id)}
                          disabled={!canManage || actionLoading === item.run_id}
                        >
                          Reject
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="mt-3 text-xs text-muted-foreground">
            Admin permission required to approve or reject.
          </p>
          {!isAdmin && (
            <p className="text-xs text-muted-foreground">You have read-only access.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
