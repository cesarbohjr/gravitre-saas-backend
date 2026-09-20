/**
 * UX/UI 3.0 Plus harness fixtures — clearly fictional (Northwind Logistics).
 * Shapes match production contracts; not live tenant data.
 */

export const HARNESS_FIXTURE_LABEL =
  "Harness fixture · Northwind Logistics · not live telemetry"

export type HarnessLens = "knows" | "learns" | "predicts" | "acts" | "improves"

export type HarnessGraphNode = {
  id: string
  kind: string
  label: string
  sublabel?: string
  state?: "idle" | "active" | "learned" | "warning"
  x: number
  y: number
}

export type HarnessGraphEdge = {
  id: string
  fromId: string
  toId: string
  label?: string
  state?: "idle" | "active" | "learned"
}

export type HarnessChangeEvent = {
  id: string
  kind: "learn" | "predict" | "signal" | "review"
  title: string
  summary: string
  at: string
  entityIds: string[]
  evidence?: string
}

export type HarnessTraceStage = {
  id: string
  label: string
  status: "pending" | "running" | "waiting" | "verified" | "failed"
  summary: string
  durationMs?: number
  startedAt?: string
  evidence?: string[]
  actor?: string
}

export type HarnessOutcome = {
  id: string
  title: string
  status: "succeeded" | "failed" | "running"
  runId: string
  createdAt: string
  stages: HarnessTraceStage[]
}

export const HARNESS_GRAPH_NODES: HarnessGraphNode[] = [
  { id: "core", kind: "hub", label: "Intelligence", sublabel: "Northwind", state: "active", x: 400, y: 220 },
  { id: "sales", kind: "department", label: "Sales", state: "idle", x: 180, y: 120 },
  { id: "support", kind: "department", label: "Support", state: "learned", x: 180, y: 320 },
  { id: "agent-ae", kind: "agent", label: "AE Router", sublabel: "Agent", state: "active", x: 620, y: 140 },
  { id: "hubspot", kind: "connector", label: "HubSpot", state: "learned", x: 620, y: 300 },
  { id: "signal-churn", kind: "signal", label: "Churn risk", sublabel: "Predicted", state: "warning", x: 400, y: 80 },
  { id: "outcome-jane", kind: "outcome", label: "Contact created", state: "learned", x: 400, y: 360 },
]

export const HARNESS_GRAPH_EDGES: HarnessGraphEdge[] = [
  { id: "e1", fromId: "sales", toId: "core", label: "feeds", state: "active" },
  { id: "e2", fromId: "support", toId: "core", label: "feeds", state: "learned" },
  { id: "e3", fromId: "core", toId: "agent-ae", label: "delegates", state: "active" },
  { id: "e4", fromId: "agent-ae", toId: "hubspot", label: "writes", state: "learned" },
  { id: "e5", fromId: "signal-churn", toId: "core", label: "predicts", state: "active" },
  { id: "e6", fromId: "hubspot", toId: "outcome-jane", label: "verified", state: "learned" },
]

export const HARNESS_CHANGE_EVENTS: HarnessChangeEvent[] = [
  {
    id: "ce1",
    kind: "learn",
    title: "Support ↔ Sales context linked",
    summary: "Ticket themes now strengthen deal-stage predictions.",
    at: "12m ago",
    entityIds: ["support", "sales", "core"],
    evidence: "relationship.promote",
  },
  {
    id: "ce2",
    kind: "predict",
    title: "Churn risk elevated for Tier-2 accounts",
    summary: "Open tickets + slower response correlate with renewal window.",
    at: "28m ago",
    entityIds: ["signal-churn", "support"],
    evidence: "prediction.score",
  },
  {
    id: "ce3",
    kind: "signal",
    title: "HubSpot write verified",
    summary: "Read-after-write matched contact 40118.",
    at: "1h ago",
    entityIds: ["hubspot", "outcome-jane"],
    evidence: "run outcome",
  },
  {
    id: "ce4",
    kind: "review",
    title: "Policy review suggested",
    summary: "New connector scope exceeds default write policy.",
    at: "2h ago",
    entityIds: ["agent-ae"],
    evidence: "policy",
  },
]

export const HARNESS_OUTCOMES: HarnessOutcome[] = [
  {
    id: "bo_01hq8s4m2k",
    title: "Created HubSpot contact for Jane Doe",
    status: "succeeded",
    runId: "run_01hq8s4m2k",
    createdAt: "6m ago",
    stages: [
      { id: "intent", label: "Intent", status: "verified", summary: "Create CRM contact from LinkedIn profile.", durationMs: 120 },
      { id: "plan", label: "Plan", status: "verified", summary: "Match person → search HubSpot → propose create.", durationMs: 890 },
      { id: "agent", label: "Agent", status: "verified", summary: "AE Router delegated enrichment.", actor: "AE Router", durationMs: 420 },
      { id: "tool", label: "Tool", status: "verified", summary: "apollo.people.match · hubspot.contacts.search", durationMs: 1240 },
      { id: "action", label: "Action", status: "verified", summary: "hubspot.contact.create", durationMs: 680 },
      { id: "result", label: "Result", status: "verified", summary: "Contact 40118 created.", durationMs: 90 },
      { id: "verification", label: "Verification", status: "verified", summary: "Read-after-write confirmed email match.", evidence: ["run outcome", "HubSpot re-read"], durationMs: 310 },
      { id: "outcome", label: "Outcome", status: "verified", summary: "Business outcome recorded.", durationMs: 40 },
    ],
  },
  {
    id: "bo_failed_sync",
    title: "Salesforce opportunity sync failed",
    status: "failed",
    runId: "run_01hq8fail",
    createdAt: "22m ago",
    stages: [
      { id: "intent", label: "Intent", status: "verified", summary: "Sync closed-won opportunities.", durationMs: 95 },
      { id: "plan", label: "Plan", status: "verified", summary: "Pull Salesforce → normalize → write warehouse.", durationMs: 720 },
      { id: "agent", label: "Agent", status: "verified", summary: "Ops Coordinator", actor: "Ops Coordinator", durationMs: 380 },
      { id: "tool", label: "Tool", status: "failed", summary: "salesforce.opportunities.list — OAuth scope insufficient.", durationMs: 2100 },
      { id: "result", label: "Result", status: "pending", summary: "Not reached.", durationMs: 0 },
      { id: "verification", label: "Verification", status: "pending", summary: "Not reached.", durationMs: 0 },
      { id: "outcome", label: "Outcome", status: "pending", summary: "Not reached.", durationMs: 0 },
    ],
  },
]

export const TRACE_STAGE_ORDER = [
  "intent",
  "plan",
  "agent",
  "tool",
  "action",
  "result",
  "verification",
  "outcome",
] as const
