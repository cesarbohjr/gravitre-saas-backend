"use client"

import type { ReactNode } from "react"
import { usePathname } from "next/navigation"
import { AgentsToaster } from "./agents-toaster"
import { AgentsConfirmHost } from "./confirm"
import { AgentsSurfaceContext, isAgentsSurfacePath } from "./surface-context"
import "./overlays.css"

/** Marks the Agents surface and mounts its toaster and confirm host. */
export function AgentsSurfaceProvider({ children }: { children: ReactNode }) {
  const active = isAgentsSurfacePath(usePathname())
  return (
    <AgentsSurfaceContext.Provider value={active}>
      {children}
      {active ? (
        <>
          <AgentsToaster />
          <AgentsConfirmHost />
        </>
      ) : null}
    </AgentsSurfaceContext.Provider>
  )
}
