"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import { fetchWorkflows, type WorkflowListItem } from "@/lib/workflows-api";
import { getEnvironmentHeader } from "@/lib/environment";
import { fetchBillingStatus, type BillingStatus } from "@/lib/billing-api";
import { UpgradeCta } from "@/components/billing/upgrade-cta";

export default function WorkflowsListPage() {
  const auth = useAuth();
  const [workflows, setWorkflows] = useState<WorkflowListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null);
  const environment = getEnvironmentHeader();

  useEffect(() => {
    if (auth.status !== "authenticated" || auth.orgId == null) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchWorkflows(auth.token)
      .then((data) => {
        if (!cancelled) setWorkflows(data.workflows);
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
  }, [auth.status, auth.token, auth.orgId]);

  useEffect(() => {
    if (auth.status !== "authenticated") return;
    fetchBillingStatus(auth.token).then(setBillingStatus).catch(() => null);
  }, [auth.status, auth.token]);

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Workflows</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to view workflows."}
          </p>
        </CardContent>
      </Card>
    );
  }

  if (auth.orgId == null) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Workflows</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Onboarding pending. Contact admin for org access to use workflows.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Workflows</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  const workflowsLimit = billingStatus?.plan.workflows_limit ?? null;
  const limitReached = workflowsLimit !== null && workflows.length >= workflowsLimit;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">
            Workflows
          </h1>
          <p className="text-sm text-muted-foreground">
            Environment: <span className="font-medium text-foreground">{environment}</span>
          </p>
        </div>
        <Link href="/workflows/new" passHref legacyBehavior>
          <Button variant="primary" size="md" asChild>
            <a>New workflow</a>
          </Button>
        </Link>
      </div>

      {limitReached && (
        <UpgradeCta message="You have reached your workflow limit. Upgrade to create more workflows." />
      )}

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Definitions</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : workflows.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No workflows yet. Create one with &quot;New workflow&quot; or run a
              dry-run with an inline definition.
            </p>
          ) : (
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-2 pr-4 font-medium text-foreground">Name</th>
                  <th className="py-2 pr-4 font-medium text-foreground">
                    Schema
                  </th>
                  <th className="py-2 font-medium text-foreground">Updated</th>
                </tr>
              </thead>
              <tbody>
                {workflows.map((w) => (
                  <tr
                    key={w.id}
                    className="border-b border-border hover:bg-muted/50"
                  >
                    <td className="py-3 pr-4">
                      <Link
                        href={`/workflows/${w.id}`}
                        className="text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                      >
                        {w.name}
                      </Link>
                      <p className="text-xs text-muted-foreground mt-1">
                        Orchestration view and execution flow
                      </p>
                    </td>
                    <td className="py-3 pr-4 text-muted-foreground">
                      {w.schema_version}
                    </td>
                    <td className="py-3 text-muted-foreground">
                      {new Date(w.updated_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
