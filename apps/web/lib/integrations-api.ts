import { getEnvironmentHeader } from "@/lib/environment";

const API = "/api/v1/integrations";

export type IntegrationItem = {
  id: string;
  type: "slack" | "email" | "webhook";
  status: "active" | "inactive" | "error";
  config: Record<string, unknown>;
  environment?: string;
  updated_at?: string;
};

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

export async function fetchIntegrations(token: string): Promise<{ integrations: IntegrationItem[] }> {
  const res = await fetch(API, { headers: headers(token), cache: "no-store" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function fetchIntegration(token: string, id: string): Promise<IntegrationItem> {
  const res = await fetch(`${API}/${id}`, { headers: headers(token), cache: "no-store" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function createIntegration(
  token: string,
  payload: { type: "slack" | "email" | "webhook"; config: Record<string, unknown> }
): Promise<IntegrationItem> {
  const res = await fetch(API, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function updateIntegration(
  token: string,
  id: string,
  payload: { config?: Record<string, unknown>; status?: "active" | "inactive" | "error" }
): Promise<IntegrationItem> {
  const res = await fetch(`${API}/${id}`, {
    method: "PATCH",
    headers: headers(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export async function setIntegrationSecret(
  token: string,
  id: string,
  payload: { key_name: string; value: string }
): Promise<{ key_name: string; message: string }> {
  const res = await fetch(`${API}/${id}/secrets`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? "Request failed", res.status);
  }
  return res.json();
}
