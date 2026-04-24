import { getEnvironmentHeader } from "@/lib/environment";

const API = "/api/v1/billing";

export type BillingPlan = {
  code: string;
  name: string;
  price_usd: number | null;
  agents_limit: number | null;
  workflows_limit: number | null;
  environments_limit: number | null;
  ai_credits_included: number;
  workflow_runs_included: number;
  features: Record<string, unknown>;
  overage_rates: Record<string, unknown>;
};

export type BillingStatus = {
  plan: BillingPlan;
  basePlan: BillingPlan;
  overridesActive: boolean;
  overrides: Record<string, unknown>;
  billingStatus: string;
  currentPeriodEnd: string | null;
  cancelAtPeriodEnd: boolean;
  usage: {
    aiCredits: {
      used: number;
      included: number;
      remaining: number;
      percent: number;
      warning: boolean;
      overage: number;
    };
    workflowRuns: {
      used: number;
      included: number;
      remaining: number;
      percent: number;
      warning: boolean;
      overage: number;
    };
    operatorUsage: { used: number };
    ragUsage: { used: number };
  };
  period: { start: string; end: string; environment: string };
};

function headers(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
    "X-Environment": getEnvironmentHeader(),
  };
}

export async function fetchBillingPlans(token: string): Promise<{ plans: BillingPlan[] }> {
  const res = await fetch(`${API}/plans`, {
    headers: headers(token),
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data;
}

export async function fetchBillingStatus(token: string): Promise<BillingStatus> {
  const res = await fetch(`${API}/status`, {
    headers: headers(token),
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data;
}

export async function createCheckoutSession(token: string, planCode: string) {
  const res = await fetch(`${API}/checkout`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify({ planCode }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data as { url: string };
}

export async function createPortalSession(token: string) {
  const res = await fetch(`${API}/portal`, {
    method: "POST",
    headers: headers(token),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data as { url: string };
}
