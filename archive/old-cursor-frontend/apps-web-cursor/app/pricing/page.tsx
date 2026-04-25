"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/lib/use-auth";
import { createCheckoutSession, fetchBillingPlans, type BillingPlan } from "@/lib/billing-api";

function formatPrice(price: number | null) {
  if (price == null) return "Custom";
  return `$${price.toFixed(0)}/mo`;
}

function limitLabel(value: number | null) {
  if (value == null) return "Unlimited";
  return value.toLocaleString();
}

function featureLabel(value: unknown) {
  if (value === true) return "Included";
  if (value === false || value == null) return "Not included";
  if (typeof value === "string") return value.charAt(0).toUpperCase() + value.slice(1);
  return "Not included";
}

const FEATURE_ORDER: Array<{ key: string; label: string }> = [
  { key: "approvals", label: "Approvals" },
  { key: "audit_logs", label: "Audit logs" },
  { key: "versioning", label: "Versioning" },
  { key: "advanced_connectors", label: "Advanced connectors" },
  { key: "rbac", label: "RBAC" },
];

export default function PricingPage() {
  const auth = useAuth();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [isCheckoutLoading, setIsCheckoutLoading] = useState<string | null>(null);
  const isAdmin = auth.status === "authenticated" && auth.role === "admin";

  useEffect(() => {
    if (auth.status !== "authenticated") {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    fetchBillingPlans(auth.token)
      .then((data) => setPlans(data.plans))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load plans."))
      .finally(() => setLoading(false));
  }, [auth.status, auth.token]);

  const handleCheckout = async (planCode: string) => {
    if (auth.status !== "authenticated") return;
    setCheckoutError(null);
    setIsCheckoutLoading(planCode);
    try {
      const res = await createCheckoutSession(auth.token, planCode);
      window.location.href = res.url;
    } catch (e) {
      setCheckoutError(e instanceof Error ? e.message : "Checkout failed.");
    } finally {
      setIsCheckoutLoading(null);
    }
  };

  if (auth.status === "loading") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">Loading…</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">Pricing</h1>
        <p className="text-sm text-muted-foreground">
          Pick the plan that fits your automation volume. Upgrade anytime.
        </p>
      </div>

      {loading ? (
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Loading plans…</p>
          </CardContent>
        </Card>
      ) : error ? (
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 md:grid-cols-3">
          {plans.map((plan) => (
            <Card key={plan.code} className="border-border bg-[hsl(var(--surface))]">
              <CardHeader>
                <CardTitle className="text-lg">{plan.name}</CardTitle>
                <p className="text-2xl font-semibold text-foreground">{formatPrice(plan.price_usd)}</p>
              </CardHeader>
              <CardContent className="space-y-4 text-sm text-muted-foreground">
                <div>
                  <div className="font-medium text-foreground">Limits</div>
                  <ul className="mt-2 space-y-1">
                    <li>Agents: {limitLabel(plan.agents_limit)}</li>
                    <li>Workflows: {limitLabel(plan.workflows_limit)}</li>
                    <li>Environments: {limitLabel(plan.environments_limit)}</li>
                    <li>AI credits: {plan.ai_credits_included.toLocaleString()}</li>
                    <li>Workflow runs: {plan.workflow_runs_included.toLocaleString()}</li>
                  </ul>
                </div>
                <div>
                  <div className="font-medium text-foreground">Features</div>
                  <ul className="mt-2 space-y-1">
                    {FEATURE_ORDER.map((feature) => (
                      <li key={feature.key} className="flex justify-between">
                        <span>{feature.label}</span>
                        <span className="text-foreground">
                          {featureLabel(plan.features?.[feature.key])}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <div className="font-medium text-foreground">Overage</div>
                  <ul className="mt-2 space-y-1">
                    <li>
                      AI credits:{" "}
                      <span className="text-foreground">
                        {plan.overage_rates?.ai_credit != null
                          ? `$${Number(plan.overage_rates.ai_credit).toFixed(3)}`
                          : "Custom"}
                      </span>
                    </li>
                    <li>
                      Workflow runs:{" "}
                      <span className="text-foreground">
                        {plan.overage_rates?.workflow_runs_per_1000 != null
                          ? `$${Number(plan.overage_rates.workflow_runs_per_1000)} / 1000`
                          : "Custom"}
                      </span>
                    </li>
                  </ul>
                </div>
                {plan.code !== "enterprise" ? (
                  <Button
                    variant="primary"
                    size="sm"
                    disabled={!isAdmin || isCheckoutLoading === plan.code}
                    onClick={() => handleCheckout(plan.code)}
                  >
                    {isCheckoutLoading === plan.code ? "Redirecting…" : "Upgrade"}
                  </Button>
                ) : (
                  <Button variant="secondary" size="sm" disabled>
                    Contact sales
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {checkoutError && (
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">{checkoutError}</p>
          </CardContent>
        </Card>
      )}

      {!isAdmin && auth.status === "authenticated" && (
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">
              Admin role required to start checkout.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
