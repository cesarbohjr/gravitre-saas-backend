/** Customer-consented MSP delegation API.
 *
 * This is not an organization switch. Every request is checked by FastAPI.
 * Keep UI disabled until live security acceptance and rollout approval.
 */
import { apiFetch } from "@/lib/fetcher"

export type MspAccessTier = 1 | 2 | 3
export type MspAction =
  | "account.health.read"
  | "usage.aggregate.read"
  | "billing.summary.read"
  | "agent.configure"
  | "workflow.manage"
  | "connector.configure"
  | "conversation.read"
  | "document.read"
  | "memory.read"

export interface MspGrantRequest {
  provider_org_id: string
  customer_org_id: string
  grantee_user_id: string
  tier: MspAccessTier
  actions: MspAction[]
  expires_at: string
}

export interface MspGrantResult {
  id: string
  status: "stored_not_activated"
}

export interface MspRevocationResult {
  id: string
  revoked: boolean
}

export interface MspCustomerHealth {
  customer_org_id: string
  status: string | null
}

async function mspRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await apiFetch(path, options)
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : `MSP request failed (${response.status})`
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export const mspDelegationsApi = {
  create: (grant: MspGrantRequest) =>
    mspRequest<MspGrantResult>("/api/msp/delegations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(grant),
    }),

  revoke: (delegationId: string, customerOrgId: string) =>
    mspRequest<MspRevocationResult>(
      `/api/msp/delegations/${encodeURIComponent(delegationId)}/revoke?customer_org_id=${encodeURIComponent(customerOrgId)}`,
      { method: "POST" },
    ),

  health: (customerOrgId: string, providerOrgId: string) =>
    mspRequest<MspCustomerHealth>(
      `/api/msp/delegations/customer/${encodeURIComponent(customerOrgId)}/health?provider_org_id=${encodeURIComponent(providerOrgId)}`,
    ),
}
