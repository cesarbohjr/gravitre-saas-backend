"use client"

/**
 * useGravitreAIShortcut — Phase 3 of the "Gravitre AI Agent Workspace"
 * redesign ("keyboard shortcut (audited against existing shortcuts first)").
 *
 * ## Audit (performed before picking a combination)
 *
 * Grepped this repo (`apps/web`) for every existing global `keydown`
 * listener before choosing anything:
 *
 *  - `Cmd/Ctrl+K` — command palette / universal search
 *    (`components/gravitre/command-palette.tsx:88`)
 *  - `Cmd/Ctrl+B` — collapse/expand the sidebar rail
 *    (`hooks/use-global-work-shortcuts.ts:24`)
 *  - `Cmd/Ctrl+N` — context-dependent "new" (agent/workflow/assignment/ai)
 *    (`hooks/use-global-work-shortcuts.ts:30`)
 *  - bare `/` (no modifier) — focus search
 *    (`hooks/use-global-work-shortcuts.ts:51`)
 *  - `Escape` — close the (separate, legacy) global command bar
 *    (`components/gravitre/global-command-bar.tsx:131`)
 *
 * None of those use `Shift+L`. Chosen combination: **Ctrl+Shift+L**
 * (Cmd+Shift+L on Mac). Verified NOT a default Chrome or Firefox shortcut
 * (checked against Google's and Mozilla's own published shortcut lists).
 * Microsoft Edge binds `Ctrl+Shift+L` to "paste and go/search" — but only
 * when the address bar itself already has focus, which cannot coexist with
 * this listener firing (the page has no focus at that point, so our
 * `keydown` handler never receives the event either way) — not a real
 * conflict for a page-level listener. 1Password's browser extension binds
 * `Ctrl+Shift+L` to "lock the extension" for users who have that extension
 * installed and have not remapped it — a real, disclosed, low-probability
 * third-party extension collision, not a browser/OS-level one, and not
 * something a web page can detect or avoid.
 *
 * Behavior: opens the Gravitre AI Float window (navigating to `/ai` first
 * if elsewhere, matching Helper's existing pattern) when closed; toggles it
 * back down to the Helper bubble when already open — satisfying "allow a
 * fast hide/minimize" with the same single combination.
 *
 * Gated behind `GRAVITRE_AI_FLOAT_ENABLED`: the listener is not attached at
 * all when the flag is off (verified in
 * `__tests__/gravitre/use-gravitre-ai-shortcut.test.ts`).
 */

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { GRAVITRE_AI_FLOAT_ENABLED } from "@/lib/ai-workspace-flags"
import { isEditableTarget } from "@/lib/work-page-shortcuts"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"

export function useGravitreAIShortcut(): void {
  const router = useRouter()
  const { pageContext, floatWorkspaceOpen, setFloatWorkspaceOpen, setPresentationMode } = useGravitreAIWorkspace()

  useEffect(() => {
    if (!GRAVITRE_AI_FLOAT_ENABLED) return

    const onKeyDown = (event: KeyboardEvent) => {
      const mod = event.metaKey || event.ctrlKey
      if (!mod || !event.shiftKey) return
      if (event.key.toLowerCase() !== "l") return
      if (isEditableTarget(event.target)) return

      event.preventDefault()

      if (floatWorkspaceOpen) {
        // Fast hide/minimize — back to the Helper bubble.
        setPresentationMode("expanded")
        setFloatWorkspaceOpen(false)
        return
      }

      setPresentationMode("float")
      setFloatWorkspaceOpen(true)
      const path = pageContext.pathname
      if (path !== "/ai" && !path.startsWith("/ai/")) {
        router.push("/ai")
      }
    }

    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [floatWorkspaceOpen, pageContext.pathname, router, setFloatWorkspaceOpen, setPresentationMode])
}
