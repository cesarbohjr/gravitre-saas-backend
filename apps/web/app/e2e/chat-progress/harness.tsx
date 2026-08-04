/**
 * Visual harness for the Chat progress UX states (COMP 4).
 *
 * The side panel is driven by live SSE `progressSteps`, which a static fixture
 * cannot produce — so this mounts TaskSidePanel / ResearchPlanPanel directly
 * with realistic props to make the mid-run, complete, and empty states
 * reviewable. Gated behind PLAYWRIGHT_E2E in page.tsx, same as the
 * execution-result harness.
 */
"use client"

import { ResearchPlanPanel } from "@/components/gravitre/assistant/research-plan-panel"
import { TaskSidePanel } from "@/components/gravitre/assistant/task-side-panel"
import type { HostedFileRef } from "@/components/gravitre/assistant/file-reference-chip"

const MID_RUN_STEPS = [
  "Completed: Search contacts in Apollo",
  "Completed: Check connector status",
  "Running: Create contact list",
  "Step 4/4: Add contacts to list",
]

const COMPLETE_STEPS = [
  "Completed: Search contacts in Apollo",
  "Completed: Check connector status",
  "Completed: Create contact list",
  "Completed: Add contacts to list",
]

const HOSTED_FILES: HostedFileRef[] = [
  {
    id: "file_1",
    filename: "apollo-contacts-q1.csv",
    role: "csv",
    mime_type: "text/csv",
    byte_size: 20_984,
    download_url: "#",
  },
]

const PENDING_TASK = {
  params: {
    integration: "apollo",
    invoke_action: "Create contact list",
    steps: [
      { label: "Search contacts in Apollo" },
      { label: "Check connector status" },
      { label: "Create contact list" },
      { label: "Add contacts to list" },
    ],
    current_step_index: 2,
  },
} as never

function Case({
  title,
  note,
  children,
}: {
  title: string
  note: string
  children: React.ReactNode
}) {
  return (
    <section className="flex flex-col gap-2">
      <div>
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
        <p className="text-xs text-muted-foreground">{note}</p>
      </div>
      {children}
    </section>
  )
}

export function ChatProgressHarness() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-8 p-6" data-testid="chat-progress-harness">
      <header>
        <h1 className="text-lg font-semibold text-foreground">Chat progress UX — states</h1>
        <p className="text-sm text-muted-foreground">
          Named step labels only. Raw &quot;Running:&quot; / &quot;Completed:&quot; prefixes must not appear.
        </p>
      </header>

      <Case title="Inline plan bar — mid-run" note="Under-threshold turns use this alone (no panel).">
        <ResearchPlanPanel cascade={null} progressSteps={MID_RUN_STEPS} strategicPlan={null} />
      </Case>

      <div className="grid gap-8 lg:grid-cols-3">
        <Case title="Panel — mid-run" note="Mixed done / current / pending.">
          <TaskSidePanel
            conversationId="conv_demo"
            progressSteps={MID_RUN_STEPS}
            pendingTask={PENDING_TASK}
            contextExplanation="Using your connected Apollo workspace."
          />
        </Case>

        <Case title="Panel — complete + outputs" note="All checks, hosted file in Outputs.">
          <TaskSidePanel
            conversationId="conv_demo"
            progressSteps={COMPLETE_STEPS}
            pendingTask={PENDING_TASK}
            contextExplanation="Using your connected Apollo workspace."
            hostedFiles={HOSTED_FILES}
          />
        </Case>

        <Case title="Panel — empty outputs / context" note="Planned steps only, nothing produced yet.">
          <TaskSidePanel conversationId="conv_empty" progressSteps={null} pendingTask={PENDING_TASK} />
        </Case>
      </div>
    </main>
  )
}
