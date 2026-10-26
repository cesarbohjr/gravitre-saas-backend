"use client"

import type { ReactNode } from "react"
import { IntelligenceConfirmHost } from "./confirm"
import { IntelligenceToaster } from "./intelligence-toaster"
import "./overlays.css"

/**
 * Mounts the Intelligence toaster and confirm host for the pages inside it
 * (the Intelligence and Models layouts). Other surfaces keep their own
 * overlays: toasts sent from here while it is not mounted go to the Agents
 * toaster instead.
 */
export function IntelligenceOverlaysProvider({ children }: { children: ReactNode }) {
  return (
    <>
      {children}
      <IntelligenceToaster />
      <IntelligenceConfirmHost />
    </>
  )
}
