"use client"

import { createContext, useContext } from "react"
import type { CanvasWorkflowNode } from "@/lib/workflows/builder-persistence"

/**
 * Seed graph override for non-persistable builder routes. Only the
 * `/e2e/shots/builder` capture harness provides one; product routes never do.
 */
const BuilderSeedContext = createContext<CanvasWorkflowNode[] | null>(null)

export const BuilderSeedProvider = BuilderSeedContext.Provider

export function useBuilderSeed(): CanvasWorkflowNode[] | null {
  return useContext(BuilderSeedContext)
}
