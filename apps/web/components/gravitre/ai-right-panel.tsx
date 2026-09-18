"use client"

/**
 * Command OS inspector: appears only when there is something to inspect.
 * Live activity remains an overlay, not a permanent empty rail.
 */

import dynamic from "next/dynamic"
import { Button } from "@/components/ui/button"
import { TYPE, NUCLEO_SIZE } from "@/lib/design-system"
import { NucleoActivity } from "@/components/icons/nucleo/semantic"
import {
  shouldShowTaskSidePanel,
  TaskSidePanel,
} from "@/components/gravitre/assistant/task-side-panel"
import type { AdvisorBrief } from "@/components/gravitre/assistant/advisor-brief-panel"

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

  if (!showTaskPanel && !liveActivityOpen) return null

  return (
    <div className="flex h-full min-h-0 flex-col" data-gravitre-inspector="">
      {showTaskPanel ? (
        <>
          <div className="flex shrink-0 items-center justify-between border-b border-divide px-3 py-2.5">
            <p className={TYPE.eyebrow}>Inspect</p>
            <Button
              type="button"
              variant={liveActivityOpen ? "secondary" : "ghost"}
              size="sm"
              className="h-7 gap-1.5 text-[11px]"
              aria-pressed={liveActivityOpen}
              onClick={onToggleLiveActivity}
            >
              <NucleoActivity width={NUCLEO_SIZE.row} height={NUCLEO_SIZE.row} aria-hidden />
              Live activity
            </Button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <TaskSidePanel
              conversationId={conversationId}
              progressSteps={progressSteps}
              pendingTask={pendingTask}
              contextExplanation={contextExplanation}
              hostedFiles={hostedFiles}
              className="flex"
            />
          </div>
        </>
      ) : null}
      {liveActivityOpen ? <LiveActivityRail advisorBrief={advisorBrief} onClose={onToggleLiveActivity} /> : null}
    </div>
  )
}
