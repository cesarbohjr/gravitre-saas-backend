/** Match standard UUID path segments (connector ids, agent ids, etc.). */
const UUID_SEGMENT =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export function isUuidPathSegment(segment: string): boolean {
  return UUID_SEGMENT.test(segment)
}

const PARENT_FALLBACK_LABEL: Record<string, string> = {
  connectors: "Connector",
  agents: "Agent",
  workflows: "Workflow",
  models: "Model",
  runs: "Run",
  assignments: "Assignment",
  sources: "Source",
  goals: "Goal",
  deliverables: "Deliverable",
  integrations: "Integration",
}

export function fallbackEntityLabel(parentSegment: string | undefined): string {
  if (!parentSegment) return "Details"
  return PARENT_FALLBACK_LABEL[parentSegment] ?? "Details"
}
