"use client"

import { createContext, useContext } from "react"

/**
 * True on the Agents surface: the signed-in app, minus Lite, which keeps its own
 * overlays until it gets a design. Dialogs, alert dialogs and sheets read this to
 * put on the Agents shell.
 */
export const AgentsSurfaceContext = createContext(false)

export function useAgentsSurface(): boolean {
  return useContext(AgentsSurfaceContext)
}

export function isAgentsSurfacePath(pathname: string | null | undefined): boolean {
  if (!pathname) return true
  return !(pathname === "/lite" || pathname.startsWith("/lite/"))
}
