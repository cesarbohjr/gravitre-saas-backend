"use client"

import { connectorsApi } from "./api"

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
  if (!catalog.configured) throw new Error("Secure connector authorization needs administrator setup before accounts can connect.")
  const { default: Nango } = await import("@nangohq/frontend")
  const session = await connectorsApi.startManagedAuth(vendor, data)
  return new Promise<boolean>((resolve, reject) => {
    let settled = false
    let confirming = false
    const ui = new Nango().openConnectUI({
      sessionToken: session.sessionToken,
      onEvent: (event) => {
        if (settled) return
        if (event.type === "connect" && !confirming) {
          confirming = true
          void waitForManagedConnection(session.connectorId, session.attemptId).then(() => {
            settled = true; ui.close(); resolve(true)
          }).catch((error) => { settled = true; ui.close(); reject(error) })
        } else if (event.type === "close" && !confirming) {
          settled = true; ui.close(); resolve(false)
        } else if (event.type === "error" && !confirming) {
          settled = true; ui.close(); reject(new Error("Account authorization failed. Please try again."))
        }
      },
    })
  })
}
