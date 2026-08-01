/**
 * Setup readiness for workflow builder ConfigPanel (required vs optional guidance).
 */
import type { CanvasWorkflowNode, DecisionPath } from "@/lib/workflows/builder-persistence"
import { resolveConnectorBind } from "@/lib/workflows/builder-connector-bind"

export type NodeReadiness = {
  ready: boolean
  missing: string[]
  /** Short status for the banner, e.g. "Ready to connect" / "2 things left" */
  summary: string
}

function nonEmpty(value: unknown): boolean {
  return String(value ?? "").trim().length > 0
}

function namedPaths(paths: DecisionPath[] | undefined): DecisionPath[] {
  return (paths || []).filter((p) => nonEmpty(p.label))
}

function decisionGuidance(node: CanvasWorkflowNode): NodeReadiness {
  const strategy = node.decisionConfig?.strategy || "ai-assisted"
  const paths = namedPaths(node.outputPaths)
  const missing: string[] = []

  if (paths.length < 2) {
    missing.push("name at least 2 branches")
  }

  const objectiveOrInstructions =
    nonEmpty(node.decisionConfig?.objective) || nonEmpty(node.decisionConfig?.conditions)

  if (strategy === "ai-assisted" || strategy === "hybrid") {
    if (!objectiveOrInstructions) {
      missing.push("write a decision objective or AI instructions")
    }
  }

  if (strategy === "rule-based" || strategy === "hybrid") {
    const pathsNeedingCondition = paths.filter((p) => !p.isDefault && !nonEmpty(p.condition))
    if (pathsNeedingCondition.length > 0) {
      missing.push("fill When to take this branch on non-default paths")
    }
    if (strategy === "rule-based" && !nonEmpty(node.decisionConfig?.conditions) && paths.every((p) => !nonEmpty(p.condition))) {
      missing.push("add rule conditions (section or per-branch)")
    }
  }

  return finalize(missing, "Decision ready — connect each branch on the canvas")
}

function finalize(missing: string[], readySummary: string): NodeReadiness {
  if (missing.length === 0) {
    return { ready: true, missing: [], summary: readySummary }
  }
  const summary =
    missing.length === 1
      ? `1 thing left: ${missing[0]}`
      : `${missing.length} things left: ${missing.join("; ")}`
  return { ready: false, missing, summary }
}

/** Evaluate whether a canvas node has the fields needed to run usefully. */
export function evaluateNodeReadiness(node: CanvasWorkflowNode): NodeReadiness {
  const nameMissing = !nonEmpty(node.name)

  switch (node.type) {
    case "agent": {
      const missing: string[] = []
      if (nameMissing) missing.push("set a name")
      const agentId = node.config?.agent_id || node.config?.agentId
      if (!nonEmpty(agentId)) missing.push("pick an existing agent")
      const task = node.config?.task || node.description
      if (!nonEmpty(task)) missing.push("write the task / assignment")
      return finalize(missing, "Agent ready — connect to the next step")
    }
    case "task": {
      const missing: string[] = []
      if (nameMissing) missing.push("set a name")
      const instructions =
        node.config?.instruction || node.config?.instructions || node.description
      if (!nonEmpty(instructions)) missing.push("write task instructions")
      return finalize(missing, "Task ready — connect to the next step")
    }
    case "connector": {
      const missing: string[] = []
      if (nameMissing) missing.push("set a name")
      const bind = resolveConnectorBind({
        vendor: node.vendor,
        selectedAction: node.selectedAction,
        config: node.config,
      })
      if (!nonEmpty(bind.vendor)) missing.push("choose a connector vendor")
      if (!nonEmpty(bind.selectedAction) && !nonEmpty(bind.action)) {
        missing.push("select an action")
      }
      return finalize(missing, "Connector ready — connect to the next step")
    }
    case "decision":
    case "if":
    case "switch":
      return decisionGuidance(node)
    case "approval": {
      const missing: string[] = []
      if (nameMissing) missing.push("set a name")
      return finalize(missing, "Approval gate ready — connect approve/reject paths")
    }
    case "council": {
      const missing: string[] = []
      if (nameMissing) missing.push("set a name")
      const ids =
        (node.config?.agentIds as string[] | undefined) ||
        (node.config?.agent_ids as string[] | undefined) ||
        node.councilConfig?.participatingAgents?.map((a) => a.id) ||
        []
      if (!ids.length) missing.push("add participating agents")
      return finalize(missing, "Council ready — connect to the next step")
    }
    default: {
      const missing: string[] = []
      if (nameMissing) missing.push("set a name")
      return finalize(missing, "Step ready — connect to the next step")
    }
  }
}

/** Whether per-path condition inputs should show for this decision strategy. */
export function showPathConditions(
  strategy: "rule-based" | "ai-assisted" | "hybrid" | undefined,
): boolean {
  return strategy === "rule-based" || strategy === "hybrid"
}
