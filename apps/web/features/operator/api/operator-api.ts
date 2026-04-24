import { getEnvironmentHeader } from "@/lib/environment";
import type {
  ActionPlan,
  ContextPackType,
  GuardrailSummary,
  OperatorContextPack,
} from "@/features/operator/types/operator";

const API = "/api/v1/operator";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function headers(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
    "X-Environment": getEnvironmentHeader(),
  };
}

export async function fetchContextPack(
  token: string,
  type: ContextPackType,
  id: string
): Promise<OperatorContextPack> {
  const res = await fetch(`${API}/context/${type}/${id}`, {
    headers: headers(token),
    cache: "no-store",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function postActionPlan(
  token: string,
  body: {
    primary_context: { type: ContextPackType; id: string };
    related_contexts?: Array<{ type: ContextPackType; id: string }>;
    operator_goal?: string | null;
  }
): Promise<ActionPlan & { guardrails: GuardrailSummary }> {
  const res = await fetch(`${API}/action-plan`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}
