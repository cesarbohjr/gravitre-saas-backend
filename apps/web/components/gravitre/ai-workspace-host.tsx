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
import dynamic from "next/dynamic"
import { LayoutGroup } from "framer-motion"
import { GRAVITRE_AI_FLOAT_ENABLED } from "@/lib/ai-workspace-flags"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"

// Loaded on first arm only. The workspace (chat runtime, AI SDK, markdown,
// voice/Pipecat client) is most of the signed-in shell's JavaScript, and a
// static import put it in the bundle of every page even though it only mounts
// on /ai, agent chat, or when the float is opened.
const AiWorkspace = dynamic(
  () => import("@/app/(app)/ai/_components/ai-workspace").then((m) => ({ default: m.AiWorkspace })),
  { ssr: false },
)

function isWorkspaceArmPath(pathname: string): boolean {
  const path = pathname.split("?")[0] ?? ""
  if (path === "/ai" || path.startsWith("/ai/")) return true
  return /^\/agents\/[^/]+\/chat\/?$/.test(path)
}

export function GravitreAIWorkspaceHost({ fixtureBoundary = false }: { fixtureBoundary?: boolean } = {}) {
  const { floatWorkspaceOpen, pageContext } = useGravitreAIWorkspace()
  const [armed, setArmed] = useState(false)

  useEffect(() => {
    if (!GRAVITRE_AI_FLOAT_ENABLED) return
    if (floatWorkspaceOpen || isWorkspaceArmPath(pageContext.pathname)) {
      setArmed(true)
    }
  }, [floatWorkspaceOpen, pageContext.pathname])

  // Capture routes always mount their own fixture-scoped host; gating on the
  // e2e env flag let the root host render a second window in plain dev.
  const captureRoute = pageContext.pathname.startsWith("/e2e/shots/")
  if (captureRoute && !fixtureBoundary) return null
  if (!GRAVITRE_AI_FLOAT_ENABLED || !armed) return null

  return (
    <Suspense fallback={null}>
      <LayoutGroup id="gravitre-ai-workspace">
        <AiWorkspace />
      </LayoutGroup>
    </Suspense>
  )
}
