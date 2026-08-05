"use client"

import {
  shouldShowTaskSidePanel,
  TaskSidePanel,
  SIDE_PANEL_STEP_THRESHOLD,
} from "@/components/gravitre/assistant/task-side-panel"
import type { ChatPendingTask } from "@/components/gravitre/assistant/chat-execution-panel"

/**
 * Harness for Progress UX v2 — threshold gate + panel Progress section.
 * mode=on  → ≥3 steps → panel visible
 * mode=off → 1 step → panel absent (inline-only)
 */
export function TaskSidePanelHarness({ mode = "on" }: { mode?: string }) {
  const normalized = mode.toLowerCase() === "off" ? "off" : "on"

  const progressSteps =
    normalized === "off"
      ? ["Running: Search contacts"]
      : [
          "Completed: Searching the web",
          "Completed: Checking connector status",
          "Running: Create contact list",
        ]

  const pendingTask: ChatPendingTask | null =
    normalized === "off"
      ? null
      : ({
          type: "connector_orchestration",
          status: "awaiting_plan_confirm",
          params: {
            integration: "apollo",
            label: "MSP list workflow",
            steps: [
              { label: "Create contact list" },
              { label: "Search contacts" },
              { label: "Add contacts to list" },
            ],
            current_step_index: 0,
          },
        } as ChatPendingTask)

  const show = shouldShowTaskSidePanel(progressSteps, pendingTask)

  return (
    <main
      className="mx-auto flex min-h-screen max-w-5xl flex-col gap-4 p-6"
      data-testid="task-side-panel-harness"
      data-mode={normalized}
      data-threshold={SIDE_PANEL_STEP_THRESHOLD}
      data-show-panel={show ? "true" : "false"}
    >
      <h1 className="text-lg font-semibold">Task side panel harness</h1>
      <p className="text-sm text-muted-foreground">
        Threshold {SIDE_PANEL_STEP_THRESHOLD} · mode={normalized} · show={String(show)}
      </p>
      <div className="flex gap-4">
        <div className="min-w-0 flex-1 rounded-xl border border-dashed border-border/60 p-4 text-sm text-muted-foreground">
          Inline chat transcript (unchanged). BusinessOutcome card stays here when present.
        </div>
        {show ? (
          <TaskSidePanel
            conversationId="e2e-task-side-panel-convo"
            progressSteps={progressSteps}
            pendingTask={pendingTask}
            contextExplanation="Connector: apollo · Action: Create contact list"
          />
        ) : (
          <div
            data-testid="task-side-panel-absent"
            className="rounded-xl border border-dashed border-border/50 px-4 py-8 text-xs text-muted-foreground"
          >
            Panel hidden — under threshold (inline-only).
          </div>
        )}
      </div>
    </main>
  )
}
