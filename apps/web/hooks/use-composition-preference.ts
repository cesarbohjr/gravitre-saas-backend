"use client"

import { useSyncExternalStore } from "react"
import {
  readCompositionPreference,
  subscribeCompositionPreference,
  type AiWorkspaceComposition,
} from "@/lib/gravitre-ai-composition"

const serverSnapshot = (): AiWorkspaceComposition | null => null

/** Hydration-safe remembered composition (server + hydrating render see `null`). */
export function useCompositionPreference(): AiWorkspaceComposition | null {
  return useSyncExternalStore(subscribeCompositionPreference, () => readCompositionPreference(), serverSnapshot)
}
