"use client"

import { useSearchParams } from "next/navigation"

import {
  ChatExecutionPanel,
  type ChatExecutionResult,
  type ChatPendingTask,
} from "@/components/gravitre/assistant/chat-execution-panel"

const CONNECTOR_APPROVAL: ChatPendingTask = {
  type: "connector_action",
  status: "awaiting_confirm",
  params: {
    label: "Restore Edit on Opportunity for ops-integration",
    invoke_action: "salesforce.permission_set.update",
    kind: "write",
    integration: "salesforce",
    requires_approval: true,
    approval_reason: "Changes user permissions in production",
    estimated_impact: "1 permission set, 1 user",
    risk_level: "medium",
  },
}

const ORCHESTRATION_PLAN: ChatPendingTask = {
  type: "connector_orchestration",
  status: "awaiting_plan_confirm",
  params: {
    goal: "Re-route the 14 scored leads once Salesforce access is restored",
    total_steps: 4,
    steps: [
      { step_id: "s1", label: "Read the 14 held leads from Lead Triage", kind: "read" },
      { step_id: "s2", label: "Check Opportunity edit access for ops-integration", kind: "read" },
      { step_id: "s3", label: "Update owner on 14 Opportunities", kind: "write", requires_approval: true },
      {
        step_id: "s4",
        label: "Post a summary to #revops",
        kind: "write",
        supported: false,
        skip_reason: "Slack is not connected for this workspace.",
      },
    ],
  },
}

const QUEUED_APPROVAL: ChatPendingTask = {
  ...CONNECTOR_APPROVAL,
  status: "awaiting_admin_approval",
  params: { ...CONNECTOR_APPROVAL.params, approval_id: "apr_2041" },
}

const RESULT: ChatExecutionResult = {
  success: true,
  title: "Re-routed 14 leads",
  body: "All 14 Opportunities now have an owner. Nothing else in Salesforce was changed.",
  integration: "salesforce",
  result_url: "/runs/run_8812",
  what_this_means: "Lead Triage is unblocked. The next scheduled run at 12:00 will route new leads normally.",
  structured: {
    plan_id: "pl_3307",
    stepBreakdown: [
      { index: 1, stepId: "s1", label: "Read 14 held leads", success: true, summary: "14 leads loaded from Lead Triage." },
      { index: 2, stepId: "s2", label: "Verified edit access", success: true, summary: "ops-integration has Edit on Opportunity." },
      { index: 3, stepId: "s3", label: "Updated 14 owners", success: true, summary: "Owners assigned by territory." },
    ],
    rows: [
      { territory: "West", leads: "6", owner: "Dana Reyes" },
      { territory: "Central", leads: "5", owner: "Sam Okafor" },
      { territory: "East", leads: "3", owner: "Priya Nair" },
    ],
  },
  artifacts: [
    { artifact_id: "a1", kind: "report", title: "Routing summary", preview: "14 leads across 3 territories", result_url: "/runs/run_8812" },
    { artifact_id: "a2", kind: "csv", title: "routed-leads.csv", preview: "14 rows" },
  ],
}

const CONTACT_COUNT_ANSWER =
  "This HubSpot account has 57 contacts.\n\nNothing else is needed from you. If it helps, I can list them, or break them down by owner or lifecycle stage."

// A bound read as the backend sends it: the report restates the answer, so it
// belongs behind Details with the plan and observation ids.
const CONTACT_COUNT: ChatExecutionResult = {
  success: true,
  entity_type: "report",
  entity_id: "2c81a222-959b-42a5-90bc-cf2d0d3d6570",
  title: "HubSpot contacts",
  body: "This HubSpot account has 57 contacts.",
  artifacts: [
    {
      artifact_id: "report:2c81a222-959b-42a5-90bc-cf2d0d3d6570",
      kind: "table",
      title: "HubSpot contacts",
      preview: "This HubSpot account has 57 contacts.",
      source: "e5_execution_plan",
    },
  ],
  structured: {
    code: "This HubSpot account has 57 contacts.",
    previewFormat: "markdown",
    title: "HubSpot contacts",
    plan_id: "2c81a222-959b-42a5-90bc-cf2d0d3d6570",
    observation_ids: ["af5d9390-2011-4e23-b4be-808b314e3b00"],
    exportable: true,
    rows: [{ count: "57", object: "contacts", source: "hubspot.contacts.search", system: "HubSpot" }],
  },
}

const STATES = {
  approval: { mode: "confirm", pending: CONNECTOR_APPROVAL, result: null },
  plan: { mode: "confirm", pending: ORCHESTRATION_PLAN, result: null },
  queued: { mode: "awaiting_approval", pending: QUEUED_APPROVAL, result: null },
  result: { mode: null, pending: null, result: RESULT },
  contacts: { mode: null, pending: null, result: CONTACT_COUNT },
} as const

type StateKey = keyof typeof STATES

function TurnFrame({ state }: { state: StateKey }) {
  const { mode, pending, result } = STATES[state]
  const answer =
    state === "contacts"
      ? CONTACT_COUNT_ANSWER
      : state === "result"
        ? "Done. Here is what changed."
        : "Here is what I will do. Nothing writes to Salesforce until you approve."
  return (
    <section data-turn-state={state} className="flex flex-col gap-3">
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
        {answer}
      </p>
      <ChatExecutionPanel
        dialogueMode={mode}
        pendingTask={pending}
        executionResult={result}
        canApprove
        answerText={answer}
        onConfirm={() => {}}
        onReject={() => {}}
        onModify={() => {}}
      />
    </section>
  )
}

export function AiTurnShot() {
  const requested = useSearchParams().get("state")
  const states = (requested && requested in STATES ? [requested] : Object.keys(STATES)) as StateKey[]
  return (
    <main className="min-h-dvh bg-background px-6 py-10">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-12">
        {states.map((state) => (
          <TurnFrame key={state} state={state} />
        ))}
      </div>
    </main>
  )
}
