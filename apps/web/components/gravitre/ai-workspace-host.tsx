"use client"

/**
 * Phase 5 — root-mounted AiWorkspace host for cross-route Float continuity.
 *
 * When `GRAVITRE_AI_FLOAT_ENABLED` is on, one AiWorkspace instance lives above
 * AppShell and stays mounted after first arm so Helper → Float no longer needs
 * `router.push("/ai")`. Lazy-arm: mount only after `/ai*` or float open, then
 * keep mounted for the session.
 */

import { Suspense, useEffect, useState } from "react"
import { AiWorkspace } from "@/app/ai/_components/ai-workspace"
import { GRAVITRE_AI_FLOAT_ENABLED } from "@/lib/ai-workspace-flags"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"

function isAiPath(pathname: string): boolean {
  const path = pathname.split("?")[0] ?? ""
  return path === "/ai" || path.startsWith("/ai/")
}

export function GravitreAIWorkspaceHost() {
  const { floatWorkspaceOpen, pageContext } = useGravitreAIWorkspace()
  const [armed, setArmed] = useState(false)

  useEffect(() => {
    if (!GRAVITRE_AI_FLOAT_ENABLED) return
    if (floatWorkspaceOpen || isAiPath(pageContext.pathname)) {
      setArmed(true)
    }
  }, [floatWorkspaceOpen, pageContext.pathname])

  if (!GRAVITRE_AI_FLOAT_ENABLED || !armed) return null

  return (
    <Suspense fallback={null}>
      <AiWorkspace />
    </Suspense>
  )
}
