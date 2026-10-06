/**
 * Branch wiring for IF / Switch / Decision nodes.
 *
 * Each output path can point at one of the node's connections (`targetNodeId`).
 * On save, the edge to that node carries `condition.branches = [pathId]`, and the
 * run engine skips nodes on paths that were not chosen.
 */
import type { CanvasWorkflowNode, DecisionPath } from "@/lib/workflows/builder-persistence"

export const BRANCHING_NODE_TYPES = new Set(["if", "switch", "decision"])

export function isBranchingNode(node: Pick<CanvasWorkflowNode, "type">): boolean {
  return BRANCHING_NODE_TYPES.has(node.type)
}

/** Default paths for a branching node that has none yet. */
export function defaultPathsFor(type: CanvasWorkflowNode["type"]): DecisionPath[] {
  if (type === "if") {
    return [
      { id: "true", label: "True" },
      { id: "false", label: "False", isDefault: true },
    ]
  }
  if (type === "switch") {
    return [
      { id: "case-1", label: "Case 1", condition: "" },
      { id: "default", label: "Default", isDefault: true },
    ]
  }
  return [
    { id: "path-a", label: "Path A" },
    { id: "path-b", label: "Path B" },
  ]
}

/**
 * Keep path targets in step with the node's connections: drop targets that are no
 * longer connected, then give each untargeted connection to the first free path.
 * Returns the same object when nothing changes.
 */
export function reconcileBranchTargets<T extends CanvasWorkflowNode>(node: T): T {
  if (!isBranchingNode(node)) return node
  const basePaths = node.outputPaths?.length ? node.outputPaths : defaultPathsFor(node.type)
  let changed = basePaths !== node.outputPaths
  const connections = new Set(node.connections)
  let paths = basePaths.map((path) => {
    if (path.targetNodeId && !connections.has(path.targetNodeId)) {
      changed = true
      return { ...path, targetNodeId: undefined }
    }
    return path
  })
  const targeted = new Set(paths.map((p) => p.targetNodeId).filter(Boolean) as string[])
  for (const target of node.connections) {
    if (targeted.has(target)) continue
    const freeIndex = paths.findIndex((p) => !p.targetNodeId)
    if (freeIndex < 0) break
    paths = paths.map((p, i) => (i === freeIndex ? { ...p, targetNodeId: target } : p))
    targeted.add(target)
    changed = true
  }
  return changed ? { ...node, outputPaths: paths } : node
}

/** Branch ids an edge from `node` to `target` carries (empty = always taken). */
export function edgeBranchesFor(node: CanvasWorkflowNode, target: string): string[] {
  if (!isBranchingNode(node)) return []
  return (node.outputPaths ?? []).filter((p) => p.targetNodeId === target).map((p) => p.id)
}

/** Connections from a branching node that no path routes to (they would never run). */
export function unroutedConnections(node: CanvasWorkflowNode): string[] {
  if (!isBranchingNode(node)) return []
  const targeted = new Set((node.outputPaths ?? []).map((p) => p.targetNodeId).filter(Boolean))
  return node.connections.filter((c) => !targeted.has(c))
}

/** After loading from the API, rebuild path targets from the saved edge branches. */
export function restoreBranchTargets<T extends CanvasWorkflowNode>(
  nodes: T[],
  apiEdges: Array<Record<string, unknown>>,
): T[] {
  const branchesByEdge = new Map<string, string[]>()
  for (const edge of apiEdges) {
    const from = String(edge.from_node_id ?? edge.fromNodeId ?? "")
    const to = String(edge.to_node_id ?? edge.toNodeId ?? "")
    const condition = edge.condition as { branch?: unknown; branches?: unknown } | null | undefined
    const labels: string[] = []
    if (condition && typeof condition === "object") {
      if (typeof condition.branch === "string") labels.push(condition.branch)
      if (Array.isArray(condition.branches)) labels.push(...condition.branches.map(String))
    }
    if (from && to && labels.length) branchesByEdge.set(`${from}->${to}`, labels)
  }
  return nodes.map((node) => {
    if (!isBranchingNode(node) || !node.outputPaths?.length) return node
    const targetByPath = new Map<string, string>()
    for (const target of node.connections) {
      for (const pathId of branchesByEdge.get(`${node.id}->${target}`) ?? []) {
        targetByPath.set(pathId, target)
      }
    }
    return {
      ...node,
      // Saved targets used client ids that the server replaced; edges are the source of truth.
      outputPaths: node.outputPaths.map((p) => ({ ...p, targetNodeId: targetByPath.get(p.id) })),
    }
  })
}

/** Slug used by `steps.<slug>.<field>` references in conditions (matches the server). */
export function stepReferenceSlug(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
}

export const CONDITION_OPERATORS = [
  { value: "==", label: "equals" },
  { value: "!=", label: "does not equal" },
  { value: ">", label: "is greater than" },
  { value: ">=", label: "is at least" },
  { value: "<", label: "is less than" },
  { value: "<=", label: "is at most" },
  { value: "contains", label: "contains" },
  { value: "not contains", label: "does not contain" },
] as const

/** Quote a value for a condition unless it is a number, boolean or reference. */
export function conditionValueLiteral(value: string): string {
  const trimmed = value.trim()
  if (!trimmed) return "empty"
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) return trimmed
  if (/^(true|false|empty)$/i.test(trimmed)) return trimmed.toLowerCase()
  if (/^(\$|steps\.|input\.|params\.)/.test(trimmed)) return trimmed
  return `'${trimmed.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}'`
}

/** Append one `field op value` clause to an existing condition with AND / OR. */
export function appendConditionClause(
  existing: string,
  clause: { field: string; operator: string; value: string },
  join: "and" | "or",
): string {
  const field = clause.field.trim()
  if (!field) return existing
  const next = `${field} ${clause.operator} ${conditionValueLiteral(clause.value)}`
  const current = existing.trim()
  return current ? `${current} ${join} ${next}` : next
}
