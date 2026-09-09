"use client"

/**
 * GravitreAIRightPanel — Phase 3 of the "Gravitre AI Agent Workspace"
 * redesign.
 *
 * See docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
 * Part B2: "GravitreAIRightPanel = existing LiveActivityRail + TaskSidePanel,
 * composed into one panel | Minor consolidation."
 *
 * ⚠️ Honest discrepancy found and disclosed (per this phase's own "report
 * honestly rather than force-fitting" instruction), rather than silently
 * "composed":
 *
 * `TaskSidePanel` is a genuinely embeddable, non-fixed-positioned component
 * (confirmed by reading `assistant/task-side-panel.tsx` — its root is a
 * plain `<aside>` with no `fixed`/`inset-*` classes) — it drops cleanly into
 * a normal flex column, exactly like `GravitreAILeftPanel`.
 *
 * `LiveActivityRail`, however, is hard-coded `fixed inset-y-0 right-0 ...`
 * (`app/ai/_components/live-activity-rail.tsx`) with NO `md:static`
 * fallback the way `ConversationSidebar` has — it is a viewport-edge
 * overlay drawer by construction, at every breakpoint, today. That matches
 * the architecture doc's OWN Part A3 finding: "Right | LiveActivityRail
 * (toggle) + inline TaskSidePanel" — i.e. even on today's real `/ai` page,
 * LiveActivityRail is already a toggled overlay, not a static embedded
 * column. Rewriting it to be embeddable would mean changing a shared
 * component's positioning contract for every one of its current callers —
 * real, non-trivial risk for a component `/ai` already depends on, and out
 * of proportion to this phase's UI-wiring scope.
 *
 * Resolution taken here (disclosed, not silent): `GravitreAIRightPanel`
 * embeds `TaskSidePanel` inline as its static default content (genuine
 * reuse, zero fork), and exposes a "Live activity" toggle that opens the
 * EXISTING `LiveActivityRail` exactly as `/ai` already does — same
 * component, same props, same fixed-overlay behavior, zero duplicated
 * data-fetching. This preserves "reused as-is" for both components; it
 * does not force LiveActivityRail into a column shape it was never built
 * for.
 */

import dynamic from "next/dynamic"
import { Activity } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { TYPE } from "@/lib/design-system"
import {
  shouldShowTaskSidePanel,
  TaskSidePanel,
} from "@/components/gravitre/assistant/task-side-panel"
import type { AdvisorBrief } from "@/components/gravitre/assistant/advisor-brief-panel"

// Same lazy-load convention `ai-workspace.tsx` already uses for this
// component — preserved here rather than switching to a static import, so
// this panel doesn't change LiveActivityRail's existing code-splitting.
const LiveActivityRail = dynamic(
  () => import("@/app/ai/_components/live-activity-rail").then((module) => ({ default: module.LiveActivityRail })),
  { ssr: false, loading: () => null },
)

type TaskSidePanelProps = Parameters<typeof TaskSidePanel>[0]

export interface GravitreAIRightPanelProps {
  progressSteps?: TaskSidePanelProps["progressSteps"]
  pendingTask?: TaskSidePanelProps["pendingTask"]
  contextExplanation?: TaskSidePanelProps["contextExplanation"]
  hostedFiles?: TaskSidePanelProps["hostedFiles"]
  conversationId?: TaskSidePanelProps["conversationId"]
  advisorBrief?: AdvisorBrief | null
  liveActivityOpen: boolean
  onToggleLiveActivity: () => void
}

export function GravitreAIRightPanel({
  progressSteps,
  pendingTask,
  contextExplanation,
  hostedFiles,
  conversationId,
  advisorBrief = null,
  liveActivityOpen,
  onToggleLiveActivity,
}: GravitreAIRightPanelProps) {
  const showTaskPanel = shouldShowTaskSidePanel(progressSteps ?? null, pendingTask ?? null)

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center justify-between border-b border-divide px-3 py-2.5">
        <p className={TYPE.eyebrow}>Context</p>
        <Button
          type="button"
          variant={liveActivityOpen ? "secondary" : "ghost"}
          size="sm"
          className="h-7 gap-1.5 text-[11px]"
          aria-pressed={liveActivityOpen}
          onClick={onToggleLiveActivity}
        >
          <Activity className="h-3 w-3" aria-hidden />
          Live activity
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {showTaskPanel ? (
          <TaskSidePanel
            conversationId={conversationId}
            progressSteps={progressSteps}
            pendingTask={pendingTask}
            contextExplanation={contextExplanation}
            hostedFiles={hostedFiles}
            className="flex"
          />
        ) : (
          <p className={cn(TYPE.meta, "px-3 py-4")}>
            No active task right now. Task progress, evidence, and outputs will appear here.
          </p>
        )}
      </div>
      {liveActivityOpen ? <LiveActivityRail advisorBrief={advisorBrief} onClose={onToggleLiveActivity} /> : null}
    </div>
  )
}
