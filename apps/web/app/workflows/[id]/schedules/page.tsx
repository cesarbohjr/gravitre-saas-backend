"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import {
  createWorkflowSchedule,
  fetchWorkflow,
  fetchWorkflowSchedules,
  updateWorkflowSchedule,
  type WorkflowDetail,
  type WorkflowSchedule,
} from "@/lib/workflows-api";
import { getEnvironmentHeader } from "@/lib/environment";

export default function WorkflowSchedulesPage() {
  const params = useParams();
  const workflowId = params.id as string;
  const auth = useAuth();
  const environment = getEnvironmentHeader();
  const [workflow, setWorkflow] = useState<WorkflowDetail | null>(null);
  const [schedules, setSchedules] = useState<WorkflowSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cronExpression, setCronExpression] = useState("@daily");
  const [enabled, setEnabled] = useState(true);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const isAdmin = auth.status === "authenticated" && auth.role === "admin";

  const load = () => {
    if (auth.status !== "authenticated" || !auth.orgId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    Promise.all([fetchWorkflow(auth.token, workflowId), fetchWorkflowSchedules(auth.token, workflowId)])
      .then(([workflowData, scheduleData]) => {
        setWorkflow(workflowData);
        setSchedules(scheduleData.schedules);
      })
      .catch((e) => setError(e.message ?? "Failed to load schedules."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [auth.status, auth.token, auth.orgId, workflowId]);

  const handleCreate = async () => {
    if (auth.status !== "authenticated" || !auth.orgId) return;
    setActionError(null);
    setActionLoading(true);
    try {
      const created = await createWorkflowSchedule(auth.token, workflowId, {
        cron_expression: cronExpression.trim(),
        enabled,
      });
      setSchedules((prev) => [created, ...prev]);
      setCronExpression("@daily");
      setEnabled(true);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to create schedule.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleToggle = async (schedule: WorkflowSchedule) => {
    if (auth.status !== "authenticated" || !auth.orgId) return;
    setActionError(null);
    setActionLoading(true);
    try {
      const updated = await updateWorkflowSchedule(auth.token, schedule.id, {
        enabled: !schedule.enabled,
      });
      setSchedules((prev) => prev.map((item) => (item.id === schedule.id ? updated : item)));
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to update schedule.");
    } finally {
      setActionLoading(false);
    }
  };

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to view schedules."}
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

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link
          href={`/workflows/${workflowId}`}
          className="text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
        >
          ← Workflow
        </Link>
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">
            Schedules
          </h1>
          <p className="text-sm text-muted-foreground">
            {workflow?.name ?? "Workflow"} · Environment:{" "}
            <span className="font-medium text-foreground">{environment}</span>
          </p>
        </div>
      </div>

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Create schedule</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium text-foreground">Cron expression</label>
            <input
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={cronExpression}
              onChange={(e) => setCronExpression(e.target.value)}
              placeholder="@daily or 0 0 * * *"
              disabled={!isAdmin || actionLoading}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Supported patterns: @hourly, @daily, @weekly, @monthly, or basic 5-field cron.
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-foreground">Enabled</label>
            <select
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={enabled ? "enabled" : "disabled"}
              onChange={(e) => setEnabled(e.target.value === "enabled")}
              disabled={!isAdmin || actionLoading}
            >
              <option value="enabled">Enabled</option>
              <option value="disabled">Disabled</option>
            </select>
          </div>
          {actionError && <p className="text-sm text-destructive">{actionError}</p>}
          <Button
            variant="primary"
            size="sm"
            onClick={handleCreate}
            disabled={!isAdmin || actionLoading}
          >
            {actionLoading ? "Saving…" : "Create schedule"}
          </Button>
          {!isAdmin && (
            <p className="text-xs text-muted-foreground">Admin permission required.</p>
          )}
        </CardContent>
      </Card>

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Active schedules</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : error ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : schedules.length === 0 ? (
            <p className="text-sm text-muted-foreground">No schedules configured.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    <th className="py-2 pr-4 font-medium text-foreground">Cron</th>
                    <th className="py-2 pr-4 font-medium text-foreground">Next run</th>
                    <th className="py-2 pr-4 font-medium text-foreground">Status</th>
                    <th className="py-2 font-medium text-foreground">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {schedules.map((schedule) => (
                    <tr key={schedule.id} className="border-b border-border hover:bg-muted/50">
                      <td className="py-3 pr-4 text-muted-foreground">{schedule.cron_expression}</td>
                      <td className="py-3 pr-4 text-muted-foreground">
                        {schedule.next_run_at ? new Date(schedule.next_run_at).toLocaleString() : "—"}
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground">
                        {schedule.enabled ? "Enabled" : "Disabled"}
                      </td>
                      <td className="py-3">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleToggle(schedule)}
                          disabled={!isAdmin || actionLoading}
                        >
                          {schedule.enabled ? "Disable" : "Enable"}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
