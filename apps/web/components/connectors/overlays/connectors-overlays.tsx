"use client"

import type { ReactNode } from "react"
import { ConnectorsToaster } from "./connectors-toaster"
import "./overlays.css"

/**
 * Mounts the Connectors toaster on the connectors pages. Shared connector
 * components used on other pages (Settings, Lite) don't get it, so their
 * toasts go to the Agents shell instead.
 */
export function ConnectorsOverlaysProvider({ children }: { children: ReactNode }) {
  return (
    <>
      {children}
      <ConnectorsToaster />
    </>
  )
}
