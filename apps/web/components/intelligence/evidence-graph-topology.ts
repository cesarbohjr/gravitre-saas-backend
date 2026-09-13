import type {
  PriorityItem,
  SignalContribution,
  SignalEvidence,
  SourceStatus,
} from "./why-gravitre-panel"
import { evidenceEventCount } from "./why-gravitre-panel"

export type EvidenceGraphNodeKind = "insight" | "signal" | "source" | "gap"

export type EvidenceGraphNode = {
  id: string
  kind: EvidenceGraphNodeKind
  label: string
  sublabel?: string
  score?: number
  status?: SourceStatus
  emphasis: number
}

export type EvidenceGraphEdge = {
  id: string
  fromId: string
  toId: string
  dashed?: boolean
}

export type EvidenceGraphLayout = {
  nodes: EvidenceGraphNode[]
  edges: EvidenceGraphEdge[]
  positions: Map<string, { x: number; y: number }>
  meta: {
    totalEvidenceEvents: number
    sourceLabels: string[]
    uniqueSourceCount: number
    gaps: string[]
  }
}

const VB = { w: 640, h: 300 }

function signalNodeId(contribution: SignalContribution, index: number): string {
  return `signal:${contribution.signalId ?? index}`
}

function sourceNodeId(signalId: string, evidence: SignalEvidence, index: number): string {
  return `source:${signalId}:${evidence.sourceId ?? index}`
}

function truncateLabel(label: string, max = 28): string {
  return label.length > max ? `${label.slice(0, max - 1)}…` : label
}

/** Build nodes/edges for one priority item — pure, unit-testable. */
export function buildEvidenceGraph(item: PriorityItem): Omit<EvidenceGraphLayout, "positions"> {
  const nodes: EvidenceGraphNode[] = []
  const edges: EvidenceGraphEdge[] = []
  const sourceLabels = new Set<string>()
  let totalEvidenceEvents = 0

  const insightId = `insight:${item.workObjectId ?? item.title ?? "primary"}`
  nodes.push({
    id: insightId,
    kind: "insight",
    label: truncateLabel(item.title ?? "Priority insight", 40),
    sublabel: item.department,
    score: item.priorityScore,
    emphasis: 1,
  })

  const contributions = item.signalContributions ?? []
  contributions.forEach((contribution, signalIndex) => {
    const sid = signalNodeId(contribution, signalIndex)
    nodes.push({
      id: sid,
      kind: "signal",
      label: truncateLabel(contribution.label ?? "Signal"),
      sublabel:
        contribution.points != null
          ? `+${contribution.points.toFixed(1)} pts`
          : contribution.description
            ? truncateLabel(contribution.description, 36)
            : undefined,
      score: contribution.signalScore,
      emphasis: (contribution.points ?? 0) > 0 ? 1 : 0.55,
    })
    edges.push({ id: `edge:${insightId}:${sid}`, fromId: insightId, toId: sid })

    const evidenceRows = contribution.evidence ?? []
    evidenceRows.forEach((evidence, evidenceIndex) => {
      const eid = sourceNodeId(sid, evidence, evidenceIndex)
      const count = evidenceEventCount(evidence)
      totalEvidenceEvents += count
      const label = evidence.sourceLabel ?? "Unlabeled source"
      if (label) sourceLabels.add(label)

      nodes.push({
        id: eid,
        kind: "source",
        label: truncateLabel(label, 24),
        sublabel:
          evidence.status === "missing"
            ? "No source"
            : count > 0
              ? `${count} event${count === 1 ? "" : "s"}`
              : undefined,
        status: evidence.status,
        emphasis: evidence.status === "live_connector" ? 1 : evidence.status === "missing" ? 0.4 : 0.7,
      })
      edges.push({
        id: `edge:${sid}:${eid}`,
        fromId: sid,
        toId: eid,
        dashed: evidence.status === "missing" || evidence.status === "knowledge_fabric_only",
      })
    })
  })

  const gaps = item.gaps ?? []
  gaps.slice(0, 3).forEach((gap, index) => {
    const gid = `gap:${index}`
    nodes.push({
      id: gid,
      kind: "gap",
      label: truncateLabel(gap, 48),
      emphasis: 0.45,
    })
    edges.push({
      id: `edge:${insightId}:${gid}`,
      fromId: insightId,
      toId: gid,
      dashed: true,
    })
  })

  return {
    nodes,
    edges,
    meta: {
      totalEvidenceEvents,
      sourceLabels: [...sourceLabels],
      uniqueSourceCount: sourceLabels.size,
      gaps,
    },
  }
}

/** Radial layout: insight top-center, signals mid-arc, sources lower arc, gaps bottom. */
export function layoutEvidenceGraph(
  graph: Omit<EvidenceGraphLayout, "positions">,
): EvidenceGraphLayout {
  const positions = new Map<string, { x: number; y: number }>()
  const insight = graph.nodes.find((n) => n.kind === "insight")
  const signals = graph.nodes.filter((n) => n.kind === "signal")
  const sources = graph.nodes.filter((n) => n.kind === "source")
  const gaps = graph.nodes.filter((n) => n.kind === "gap")

  const cx = VB.w / 2

  if (insight) {
    positions.set(insight.id, { x: cx, y: 52 })
  }

  const signalY = 130
  const signalSpan = Math.min(VB.w - 80, 420)
  signals.forEach((node, i) => {
    const t = signals.length === 1 ? 0.5 : i / (signals.length - 1)
    positions.set(node.id, { x: cx - signalSpan / 2 + t * signalSpan, y: signalY })
  })

  const sourceY = 210
  sources.forEach((node, i) => {
    const t = sources.length === 1 ? 0.5 : i / (sources.length - 1)
    positions.set(node.id, { x: 40 + t * (VB.w - 80), y: sourceY })
  })

  gaps.forEach((node, i) => {
    positions.set(node.id, { x: cx, y: 255 + i * 18 })
  })

  return { ...graph, positions }
}

export const EVIDENCE_GRAPH_VB = VB
