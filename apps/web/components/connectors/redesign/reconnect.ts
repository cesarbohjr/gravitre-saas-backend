"use client"

import { toast } from "@/components/connectors/overlays/toast"
import { connectorsApi } from "@/lib/api"
import { connectorVendorKey, isManagedConnectorVendor, MANAGED_OAUTH_FALLBACK_VENDOR_KEYS } from "@/lib/connectors"
import { formatUnknownError } from "@/lib/fetcher"
import { managedProviderAvailable, openManagedConnector } from "@/lib/managed-connector-auth"

export type ReconnectTarget = {
  id: string
  name: string
  type: string
  vendorKey?: string
  authStatus?: string
  config?: Record<string, unknown> | null
}

/**
 * Re-runs the system's sign-in: the managed provider popup when the connector
 * uses one, otherwise the native OAuth redirect. Shared by the hub and the
 * detail page so both reconnect the same way.
 */
export async function reconnectConnector(connector: ReconnectTarget, onConnected?: () => Promise<unknown> | void): Promise<void> {
  const provider = connectorVendorKey(connector.vendorKey || connector.type)
  const cfg = connector.config ?? {}
  const vendor = connector.vendorKey || connector.type
  let useManaged = isManagedConnectorVendor(provider) || cfg.auth_provider === "managed" || cfg.authProvider === "managed"
  if (!useManaged && MANAGED_OAUTH_FALLBACK_VENDOR_KEYS.has(provider) && connector.authStatus === "auth_expired") {
    try {
      useManaged = managedProviderAvailable(await connectorsApi.managedCatalog(), provider)
    } catch {
      /* Native reconnect remains available. */
    }
  }
  if (useManaged) {
    try {
      const connected = await openManagedConnector(provider, { name: connector.name, connectorId: connector.id })
      if (connected) {
        toast.success(`${connector.type} reconnected`, { vendor, topic: "Reconnected", description: "Paused agents and workflows pick up on their next run." })
        await onConnected?.()
      }
    } catch (err) {
      toast.error("Failed to reconnect", { vendor, topic: "Reconnect", description: formatUnknownError(err) })
    }
    return
  }
  const extra: { subdomain?: string; instanceUrl?: string; owner?: string; repo?: string } = {}
  if (cfg.subdomain) extra.subdomain = String(cfg.subdomain)
  if (cfg.instance_url) extra.instanceUrl = String(cfg.instance_url)
  if (cfg.owner) extra.owner = String(cfg.owner)
  if (cfg.repo) extra.repo = String(cfg.repo)
  try {
    const { authorizationUrl } = await connectorsApi.reconnectOAuth(provider, connector.id, connector.name, extra)
    window.location.assign(authorizationUrl)
  } catch (err) {
    console.error("[connectors] OAuth reconnect failed:", err)
    toast.error("Failed to start OAuth", {
      vendor,
      topic: "Reconnect",
      description: err instanceof Error ? err.message : `${connector.type} OAuth may not be configured`,
    })
  }
}
