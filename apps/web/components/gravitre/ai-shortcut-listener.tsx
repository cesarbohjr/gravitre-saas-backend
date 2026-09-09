"use client"

/**
 * GravitreAIShortcutListener — Phase 3. Mounted once in `app/layout.tsx`,
 * inside `GravitreAIWorkspaceProvider`, alongside `GravitreAIHelper`.
 * Renders nothing; exists purely to call `useGravitreAIShortcut()` at a
 * stable, always-mounted location so the shortcut works from every route,
 * not just while the Helper bubble happens to be rendered.
 */

import { useGravitreAIShortcut } from "@/hooks/use-gravitre-ai-shortcut"

export function GravitreAIShortcutListener() {
  useGravitreAIShortcut()
  return null
}
