"use client"

import Link from "next/link"
import { Activity, ArrowRight, Brain } from "lucide-react"
import { cn } from "@/lib/utils"
import { APP_ROUTES } from "@/lib/app-routes"

type Surface = "operate" | "insights"

type AgentSurfaceSwitchProps = {
  surface: Surface
  /** When on a detail page, pass the same agent id so the peer link stays on that agent. */
  agentId?: string
  className?: string
}

/**
 * Clarifies the two agent surfaces and links between them.
 * - Operate (/agents): chat, knowledge, assign, constellation
 * - Insights (/intelligence/agents): health, performance, learning, outcomes
 */
export function AgentSurfaceSwitch({ surface, agentId, className }: AgentSurfaceSwitchProps) {
  const isOperate = surface === "operate"
  const peerHref = isOperate
    ? agentId
      ? `${APP_ROUTES.intelligenceAgents}/${agentId}`
      : APP_ROUTES.intelligenceAgents
    : agentId
      ? `${APP_ROUTES.agents}/${agentId}`
      : APP_ROUTES.agents

  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-xl border border-border/70 bg-background/80 p-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:p-4",
        className,
      )}
    >
      <div className="min-w-0 flex items-start gap-3">
        <div
          className={cn(
            "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
            isOperate
              ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
              : "bg-violet-500/15 text-violet-700 dark:text-violet-300",
          )}
        >
          {isOperate ? <Activity className="h-4 w-4" aria-hidden /> : <Brain className="h-4 w-4" aria-hidden />}
        </div>
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {isOperate ? "Operate · AI Team" : "Insights · Agent intelligence"}
          </p>
          <p className="mt-0.5 text-sm text-foreground">
            {isOperate
              ? "Chat, knowledge, assignments, and live team constellation."
              : "Health, performance, learning confidence, and measured outcomes."}
          </p>
        </div>
      </div>

      <Link
        href={peerHref}
        className={cn(
          "inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition",
          "border-border/80 bg-card hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      >
        {isOperate ? (
          <>
            <Brain className="h-3.5 w-3.5" aria-hidden />
            Open intelligence view
          </>
        ) : (
          <>
            <Activity className="h-3.5 w-3.5" aria-hidden />
            Open AI Team view
          </>
        )}
        <ArrowRight className="h-3.5 w-3.5" aria-hidden />
      </Link>
    </div>
  )
}
