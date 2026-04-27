import { supabaseClient } from "@/lib/supabaseClient"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import type {
  ApiAuthMe,
  ApiConnector,
  ApiMetricsOverview,
  ApiOperator,
  ApiRun,
  ApiSource,
  ApiWorkflow,
} from "@/types/api"

const FASTAPI_PREFIX = "/fastapi"

async function getAccessToken(): Promise<string | null> {
  try {
    const { data } = await supabaseClient.auth.getSession()
    return data.session?.access_token ?? null
  } catch {
    return null
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  headers.set("accept", "application/json")

  const token = await getAccessToken()
  if (token && !headers.has("authorization")) {
    headers.set("authorization", `Bearer ${token}`)
  }

  const selectedOrg = getSelectedOrgFromStorage()
  if (selectedOrg?.id && !headers.has("x-org-id")) {
    headers.set("x-org-id", selectedOrg.id)
  }

  const response = await fetch(`${FASTAPI_PREFIX}${path}`, {
    ...init,
    headers,
    cache: init?.cache ?? "no-store",
  })

  if (!response.ok) {
    throw new Error(`API request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

export const api = {
  authMe: () => request<ApiAuthMe>("/api/auth/me"),
  workflows: () => request<{ workflows: ApiWorkflow[] }>("/api/workflows"),
  runs: () => request<{ runs: ApiRun[] }>("/api/runs"),
  connectors: () => request<{ connectors: ApiConnector[] }>("/api/connectors"),
  sources: () => request<{ sources: ApiSource[] }>("/api/sources"),
  operators: () => request<{ operators?: ApiOperator[]; agents?: ApiOperator[] }>("/api/operators"),
  metricsOverview: () => request<ApiMetricsOverview>("/api/metrics/overview"),
}
