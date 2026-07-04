import { apiFetch } from "@/lib/fetcher"
import { DEFAULT_OPERATOR_CONTEXT } from "@/lib/ai-inline-execute"

type ConnectorRow = {
  id?: string
  type?: string
  vendor?: string
  status?: string
}

const ACTIVE_STATUSES = new Set(["connected", "healthy", "active"])

/** Resolve operator job context from the org's first healthy connector (not hardcoded SF). */
export async function resolveOperatorActiveContext(): Promise<string> {
  try {
    const response = await apiFetch("/api/connectors")
    if (!response.ok) return DEFAULT_OPERATOR_CONTEXT
    const payload = (await response.json()) as { connectors?: ConnectorRow[] }
    const connectors = payload.connectors ?? []
    const healthy = connectors.find((row) =>
      ACTIVE_STATUSES.has(String(row.status || "").toLowerCase()),
    )
    if (!healthy) return DEFAULT_OPERATOR_CONTEXT
    const vendor = String(healthy.type || healthy.vendor || "connector").toLowerCase()
    const id = String(healthy.id || vendor)
    return `connector-${vendor}:${id}`
  } catch {
    return DEFAULT_OPERATOR_CONTEXT
  }
}
