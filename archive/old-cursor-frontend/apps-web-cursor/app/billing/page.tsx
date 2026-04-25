"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/lib/use-auth";
import { createPortalSession, fetchBillingStatus, type BillingStatus } from "@/lib/billing-api";
import { UpgradeCta } from "@/components/billing/upgrade-cta";

function percent(value: number) {
  return `${Math.round(value)}%`;
}

function overageLabel(value: number) {
  if (!value) return null;
  return `Overage: ${value}`;
}

export default function BillingPage() {
  const auth = useAuth();
  const [status, setStatus] = useState<BillingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [portalError, setPortalError] = useState<string | null>(null);
  const [isPortalLoading, setIsPortalLoading] = useState(false);
  const isAdmin = auth.status === "authenticated" && auth.role === "admin";

  useEffect(() => {
    if (auth.status !== "authenticated") {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    fetchBillingStatus(auth.token)
      .then(setStatus)
      .catch((e) => setError(e instanceof Error ? e.message : "Billing data unavailable."))
      .finally(() => setLoading(false));
  }, [auth.status, auth.token]);

  const openPortal = async () => {
    if (auth.status !== "authenticated") return;
    setPortalError(null);
    setIsPortalLoading(true);
    try {
      const res = await createPortalSession(auth.token);
      window.location.href = res.url;
    } catch (e) {
      setPortalError(e instanceof Error ? e.message : "Portal unavailable.");
    } finally {
      setIsPortalLoading(false);
    }
  };

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to view billing."}
          </p>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Billing</CardTitle>
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
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">Billing</h1>
          <p className="text-sm text-muted-foreground">Current plan and usage.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => window.location.assign("/pricing")}>
            Upgrade
          </Button>
          <Button
            variant="primary"
            size="sm"
            disabled={!isAdmin || isPortalLoading}
            onClick={openPortal}
          >
            {isPortalLoading ? "Opening…" : "Manage billing"}
          </Button>
        </div>
      </div>

      {loading || !status ? (
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Loading billing status…</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card className="border-border bg-[hsl(var(--surface))]">
            <CardHeader>
              <CardTitle className="text-lg">Plan</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <div className="flex justify-between">
                <span>Plan</span>
                <span className="text-foreground">{status.plan.name}</span>
              </div>
              <div className="flex justify-between">
                <span>Base plan</span>
                <span className="text-foreground">{status.basePlan.name}</span>
              </div>
              <div className="flex justify-between">
                <span>Overrides</span>
                <span className="text-foreground">
                  {status.overridesActive ? "Active" : "None"}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Status</span>
                <span className="text-foreground">{status.billingStatus}</span>
              </div>
              <div className="flex justify-between">
                <span>Period end</span>
                <span className="text-foreground">{status.currentPeriodEnd ?? "—"}</span>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border bg-[hsl(var(--surface))]">
            <CardHeader>
              <CardTitle className="text-lg">Effective Limits</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <div className="flex justify-between">
                <span>Agents</span>
                <span className="text-foreground">
                  {status.plan.agents_limit ?? "Unlimited"}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Workflows</span>
                <span className="text-foreground">
                  {status.plan.workflows_limit ?? "Unlimited"}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Environments</span>
                <span className="text-foreground">
                  {status.plan.environments_limit ?? "Unlimited"}
                </span>
              </div>
              <div className="flex justify-between">
                <span>AI credits</span>
                <span className="text-foreground">{status.plan.ai_credits_included}</span>
              </div>
              <div className="flex justify-between">
                <span>Workflow runs</span>
                <span className="text-foreground">{status.plan.workflow_runs_included}</span>
              </div>
            </CardContent>
          </Card>

          {status.usage.aiCredits.warning || status.usage.workflowRuns.warning ? (
            <UpgradeCta
              message="You are nearing plan limits. Upgrade to avoid overages."
              actionLabel="Upgrade plan"
            />
          ) : null}

          <div className="grid gap-4 md:grid-cols-2">
            <Card className="border-border bg-[hsl(var(--surface))]">
              <CardHeader>
                <CardTitle className="text-lg">AI Credits</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                <div className="flex justify-between">
                  <span>Used</span>
                  <span className="text-foreground">{status.usage.aiCredits.used}</span>
                </div>
                <div className="flex justify-between">
                  <span>Included</span>
                  <span className="text-foreground">{status.usage.aiCredits.included}</span>
                </div>
                <div className="flex justify-between">
                  <span>Remaining</span>
                  <span className="text-foreground">{status.usage.aiCredits.remaining}</span>
                </div>
                <div className="text-xs text-muted-foreground">
                  {percent(status.usage.aiCredits.percent)} of credits used
                </div>
                {status.usage.aiCredits.overage > 0 ? (
                  <div className="text-xs text-amber-500">
                    {overageLabel(status.usage.aiCredits.overage)}
                  </div>
                ) : null}
              </CardContent>
            </Card>

            <Card className="border-border bg-[hsl(var(--surface))]">
              <CardHeader>
                <CardTitle className="text-lg">Workflow Runs</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                <div className="flex justify-between">
                  <span>Used</span>
                  <span className="text-foreground">{status.usage.workflowRuns.used}</span>
                </div>
                <div className="flex justify-between">
                  <span>Included</span>
                  <span className="text-foreground">{status.usage.workflowRuns.included}</span>
                </div>
                <div className="flex justify-between">
                  <span>Remaining</span>
                  <span className="text-foreground">{status.usage.workflowRuns.remaining}</span>
                </div>
                <div className="text-xs text-muted-foreground">
                  {percent(status.usage.workflowRuns.percent)} of runs used
                </div>
                {status.usage.workflowRuns.overage > 0 ? (
                  <div className="text-xs text-amber-500">
                    {overageLabel(status.usage.workflowRuns.overage)}
                  </div>
                ) : null}
              </CardContent>
            </Card>

            <Card className="border-border bg-[hsl(var(--surface))]">
              <CardHeader>
                <CardTitle className="text-lg">Operator Usage</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                <div className="flex justify-between">
                  <span>Used</span>
                  <span className="text-foreground">{status.usage.operatorUsage.used}</span>
                </div>
              </CardContent>
            </Card>

            <Card className="border-border bg-[hsl(var(--surface))]">
              <CardHeader>
                <CardTitle className="text-lg">RAG Usage</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                <div className="flex justify-between">
                  <span>Used</span>
                  <span className="text-foreground">{status.usage.ragUsage.used}</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </>
      )}

      {portalError && (
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">{portalError}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
