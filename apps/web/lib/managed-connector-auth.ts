"use client"

import { connectorsApi } from "./api"

export function managedProviderAvailable(catalog: Awaited<ReturnType<typeof connectorsApi.managedCatalog>> | undefined, vendor: string): boolean {
  return catalog?.configured === true && catalog.connectors.some((entry) => entry.vendor === vendor && entry.available === true)
}

/** Server webhook confirmation is authoritative; SDK events are only a prompt to poll. */
export async function waitForManagedConnection(connectorId: string, attemptId: string): Promise<void> {
  for (let attempt = 0; attempt < 30; attempt++) {
    const status = await connectorsApi.managedAuthStatus(connectorId)
    if (status.connected && status.confirmedAttemptId === attemptId) return
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }
  throw new Error("Authorization completed, but activation is still pending. Refresh the connector list shortly.")
}

export async function openManagedConnector(vendor: string, data: { name: string; connectorId?: string }): Promise<boolean> {
  const catalog = await connectorsApi.managedCatalog()
  const provider = catalog.connectors.find((entry) => entry.vendor === vendor)
  if (provider?.authMode && !["OAUTH1", "OAUTH2"].includes(provider.authMode)) {
    throw new Error("Sign-in authorization is not available for this provider yet.")
  }
  if (!managedProviderAvailable(catalog, vendor)) throw new Error("This provider needs administrator setup before accounts can connect.")
  const [{ default: Nango }, { showManagedOAuthDialog }] = await Promise.all([
    import("@nangohq/frontend"), import("./managed-oauth-dialog"),
  ])
  const fields = provider?.inputFields ?? []
  const prepare = (connectionConfig: Record<string, string>) => connectorsApi.startManagedAuth(vendor, { ...data, connectionConfig })
  const initialSession = fields.length ? undefined : await prepare({})
  return showManagedOAuthDialog({
    name: data.name, fields, initialSession, prepare,
    authorize: (session) => {
      // Invoked synchronously from the user's click, preserving browser popup permission.
      const client = new Nango({ connectSessionToken: session.sessionToken })
      const options = { params: session.connectionConfig ?? {}, detectClosedAuthWindow: true }
      return (session.reconnect ? client.reconnect(session.integrationId, options) : client.auth(session.integrationId, options))
        .then(() => waitForManagedConnection(session.connectorId, session.attemptId))
    },
  })
}
