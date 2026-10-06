"use client"

/**
 * The apps an agent can be scoped to: the workspace's connected connectors, one row
 * per vendor. Ids are integration keys (e.g. "hubspot", "google_analytics"), which is
 * what the backend tool registry matches an agent's `systems` against.
 */
import { useMemo } from "react"
import useSWR from "swr"
import { connectorsApi } from "@/lib/api"
import { CONNECTOR_CATALOG, connectorVendorKey } from "@/lib/connectors"

export type ConnectedAgentApp = { id: string; name: string; type: string }

const KNOWN_APP_KEYS = new Set(CONNECTOR_CATALOG.map((entry) => entry.vendorKey))

export const CONNECTED_APP_STATUSES = new Set(["connected", "healthy", "active", "syncing"])

type ConnectorRow = { status?: string | null; type?: string | null; vendor?: string | null; name?: string | null }

export function connectedAppsFromConnectors(rows: ConnectorRow[] | undefined | null): ConnectedAgentApp[] {
  const byKey = new Map<string, ConnectedAgentApp>()
  for (const row of rows ?? []) {
    if (!CONNECTED_APP_STATUSES.has(String(row.status ?? "").toLowerCase())) continue
    const id = connectorVendorKey(row.type ?? row.vendor ?? "")
    if (!id || byKey.has(id)) continue
    byKey.set(id, { id, name: row.name || row.vendor || id, type: row.vendor || row.type || "App" })
  }
  return Array.from(byKey.values()).sort((a, b) => a.name.localeCompare(b.name))
}

/**
 * Saved `systems` / `permissions` entries (keys or older display names) as integration keys.
 * A multi-word label that matches no known app (e.g. a custom scope) is kept as written
 * rather than squashed into a key nothing matches.
 */
export function agentSystemKeys(saved: string[] | undefined | null): string[] {
  const keys = (saved ?? [])
    .map((name) => {
      const raw = String(name ?? "").trim()
      const key = connectorVendorKey(raw)
      return /\s/.test(raw) && !KNOWN_APP_KEYS.has(key) ? raw : key
    })
    .filter(Boolean)
  return Array.from(new Set(keys))
}

export function useConnectedAgentApps() {
  const { data, error, isLoading } = useSWR("agent-connected-apps", () => connectorsApi.list(), {
    revalidateOnFocus: false,
  })
  const apps = useMemo(() => connectedAppsFromConnectors(data?.connectors), [data])
  return { apps, error, isLoading }
}
