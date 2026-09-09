"use client"

/**
 * useGravitreAIShortcut — Phase 3/5 of the "Gravitre AI Agent Workspace" redesign.
 *
 * Phase 5: opens/closes Float without navigating to `/ai` — the root-mounted
 * AiWorkspace host owns the live runtime across routes.
 *
 * Shortcut: Ctrl/Cmd+Shift+L (audit unchanged — see prior file header history).
 */

import { useEffect } from "react"
import { GRAVITRE_AI_FLOAT_ENABLED } from "@/lib/ai-workspace-flags"
import { isEditableTarget } from "@/lib/work-page-shortcuts"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"

export function useGravitreAIShortcut(): void {
  const { floatWorkspaceOpen, setFloatWorkspaceOpen, setPresentationMode } = useGravitreAIWorkspace()

  useEffect(() => {
    if (!GRAVITRE_AI_FLOAT_ENABLED) return

    const onKeyDown = (event: KeyboardEvent) => {
      const mod = event.metaKey || event.ctrlKey
      if (!mod || !event.shiftKey) return
      if (event.key.toLowerCase() !== "l") return
      if (isEditableTarget(event.target)) return

      event.preventDefault()

      if (floatWorkspaceOpen) {
        setPresentationMode("expanded")
        setFloatWorkspaceOpen(false)
        return
      }

      setPresentationMode("float")
      setFloatWorkspaceOpen(true)
    }

    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [floatWorkspaceOpen, setFloatWorkspaceOpen, setPresentationMode])
}
