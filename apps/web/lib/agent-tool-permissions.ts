/** Agent-specific connector/tool permissions. Backend enforces org-admin authorization.
 * Never infer access from the connector being installed or the agent's trust level.
 */
import { apiFetch, fetcher } from "@/lib/fetcher"

export interface AgentToolPermission {
  id: string
  agentId: string
  connectorId: string | null
  connectorType: string | null
  scopes: string[]
  grantedBy: string | null
  grantedAt: string | null
  expiresAt: string | null
}

export interface AgentToolPermissionGrant {
  connectorId?: string
  connectorType?: string
  scopes: string[]
  expiresAt?: string | null
}

function agentPath(agentId: string) {
  return `/api/agents/${encodeURIComponent(agentId)}/tool-permissions`
}

export const agentToolPermissionsApi = {
  list: (agentId: string) => fetcher<AgentToolPermission[]>(agentPath(agentId)),
  grant: async (agentId: string, grant: AgentToolPermissionGrant) => {
    const response = await apiFetch(agentPath(agentId), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(grant),
    })
    if (!response.ok) throw new Error(await permissionError(response))
    return response.json() as Promise<AgentToolPermission>
  },
  revoke: async (agentId: string, permissionId: string) => {
    const response = await apiFetch(
      `${agentPath(agentId)}/${encodeURIComponent(permissionId)}`,
      { method: "DELETE" },
    )
    if (!response.ok) throw new Error(await permissionError(response))
    // Successful revoke is 204 No Content; never parse a body.
  },
}

async function permissionError(response: Response): Promise<string> {
  const payload: unknown = await response.json().catch(() => null)
  if (payload && typeof payload === "object" && "detail" in payload) {
    return String((payload as { detail: unknown }).detail)
  }
  return `Permission request failed (${response.status})`
}
