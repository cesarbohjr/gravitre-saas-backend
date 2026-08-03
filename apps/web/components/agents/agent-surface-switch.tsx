"use client"

import { cn } from "@/lib/utils"

type Surface = "operate" | "insights"

type AgentSurfaceSwitchProps = {
  surface: Surface
  /** Retained for call-site compatibility after IA merge. */
  agentId?: string
  className?: string
}

/**
 * Retired dual-surface switch — Agent intelligence folded into `/agents`.
 * Kept as a no-op so existing call sites compile without layout regressions.
 */
export function AgentSurfaceSwitch({ className }: AgentSurfaceSwitchProps) {
  if (!className) return null
  return <div className={cn("hidden", className)} aria-hidden />
}
