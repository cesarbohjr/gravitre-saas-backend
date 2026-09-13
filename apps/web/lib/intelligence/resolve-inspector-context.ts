/**
 * G5 — Resolve map selection + canonical snapshot into rich inspector content.
 */
import type { IntelligencePageContextResponse } from "@/lib/api"
import type { IntelligenceMapSelection } from "@/components/intelligence/map/intelligence-map"
import type { AllDepartmentsPayload, PriorityItem } from "@/components/intelligence/why-gravitre-panel"
import { flattenPriorities } from "@/components/intelligence/why-gravitre-panel"
import { readString } from "@/lib/intelligence/helpers"

export type InspectorFact = { label: string; value: string }

export type InspectorContext = {
  eyebrow: string
  title: string
  summary?: string
  facts: InspectorFact[]
  evidence: string[]
  qualityFlags: string[]
  provenance?: string
  graphNodeId?: string
  priorityEvidence?: PriorityItem | null
  askPrompt?: string
}

function readRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {}
}

function provenanceLabel(source: unknown): string | undefined {
  const record = readRecord(source)
  const system = readString(record.system, "")
  if (!system) return undefined
  const recordId = readString(record.recordId, "")
  return recordId ? `${system} · ${recordId}` : system
}

function qualityFlagLabel(flag: string): string {
  return flag
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export function formatQualityFlags(flags: string[]): string[] {
  return [...new Set(flags.map(qualityFlagLabel))]
}

function findCanonicalAgent(
  snapshot: IntelligencePageContextResponse["snapshot"],
  agentId: string,
) {
  return snapshot.agents.find((a) => a.id === agentId)
}

function findCanonicalPrediction(
  snapshot: IntelligencePageContextResponse["snapshot"],
  predictionId: string,
) {
  return snapshot.predictions.find((p) => readString(p.id, "") === predictionId)
}

function findCanonicalLearning(
  snapshot: IntelligencePageContextResponse["snapshot"],
  learningId: string,
) {
  return snapshot.learnings.find((l) => readString(l.id, "") === learningId)
}

function findGraphNode(
  pageContext: IntelligencePageContextResponse | null | undefined,
  nodeId: string,
) {
  return pageContext?.graph?.nodes?.find((n) => readString(n.id, "") === nodeId)
}

/** Match department-scored priority evidence to a business signal or prediction. */
export function matchPriorityEvidence(
  whyData: AllDepartmentsPayload | null | undefined,
  opts: { signalTitle?: string; predictionId?: string; department?: string },
): PriorityItem | null {
  const priorities = flattenPriorities(whyData, 12)
  if (!priorities.length) return null

  const titleNeedle = (opts.signalTitle ?? "").toLowerCase()
  const deptNeedle = (opts.department ?? "").toLowerCase()

  if (titleNeedle) {
    const byTitle = priorities.find((item) =>
      (item.title ?? "").toLowerCase().includes(titleNeedle.slice(0, Math.min(titleNeedle.length, 24))),
    )
    if (byTitle) return byTitle
  }

  if (opts.predictionId) {
    const byId = priorities.find((item) => item.workObjectId === opts.predictionId)
    if (byId) return byId
  }

  if (deptNeedle) {
    const byDept = priorities.find((item) =>
      (item.department ?? "").toLowerCase().includes(deptNeedle),
    )
    if (byDept) return byDept
  }

  return null
}

export function resolveInspectorContext(
  selection: IntelligenceMapSelection,
  pageContext: IntelligencePageContextResponse | null | undefined,
  whyData?: AllDepartmentsPayload | null,
): InspectorContext | null {
  if (!selection) return null

  const snapshot = pageContext?.snapshot
  const windowHours = snapshot?.timeWindowHours ?? 24

  if (selection.kind === "agent") {
    const canonical = snapshot ? findCanonicalAgent(snapshot, selection.agent.id) : undefined
    const configured = canonical?.isConfiguredActive
      ? "Configured active"
      : "Not configured active"
    const running = canonical?.isCurrentlyRunning ? "Currently running" : "Idle in execution"
    return {
      eyebrow: "Agent",
      title: selection.agent.name,
      summary: selection.agent.role ?? undefined,
      facts: [
        { label: "Roster status", value: configured },
        { label: "Execution", value: running },
        { label: "Department", value: selection.agent.department },
        ...(canonical?.configuredStatus
          ? [{ label: "Configured status", value: String(canonical.configuredStatus) }]
          : []),
        { label: "Time window", value: `${windowHours}h` },
      ],
      evidence: [],
      qualityFlags: formatQualityFlags(pageContext?.qualityFlags ?? []),
      provenance: canonical
        ? provenanceLabel((canonical as Record<string, unknown>).source)
        : "Agent roster + operators merge",
      graphNodeId: `agent:${selection.agent.id}`,
      askPrompt: `Why is ${selection.agent.name} ${canonical?.isCurrentlyRunning ? "running" : "active"} right now?`,
    }
  }

  if (selection.kind === "signal") {
    const signal = selection.signal
    const title = readString(signal.title, "Business signal")
    const summary = readString(signal.summary, "")
    const signalId = readString(signal.id, "")
    const prediction = snapshot ? findCanonicalPrediction(snapshot, signalId) : undefined
    const evidence = prediction
      ? (prediction.evidence as string[] | undefined) ?? []
      : []
    const qualityFlags = prediction
      ? formatQualityFlags((prediction.qualityFlags as string[] | undefined) ?? [])
      : []
    const confidence = prediction?.confidence ?? signal.confidence
    const confidenceLabel =
      confidence != null && Number.isFinite(Number(confidence))
        ? `${Math.round(Number(confidence) * 100)}%`
        : "Not scored"

    const priorityEvidence = matchPriorityEvidence(whyData, {
      signalTitle: title,
      predictionId: signalId,
      department: readString(signal.department, readString(prediction?.department, "")),
    })

    return {
      eyebrow: "Prediction",
      title: prediction ? readString(prediction.businessStatement, title) : title,
      summary: summary || undefined,
      facts: [
        { label: "Confidence", value: confidenceLabel },
        ...(prediction?.department
          ? [{ label: "Department", value: String(prediction.department) }]
          : []),
        ...(prediction?.sourceModel
          ? [{ label: "Source model", value: String(prediction.sourceModel) }]
          : []),
        { label: "Time window", value: `${windowHours}h` },
      ],
      evidence,
      qualityFlags,
      provenance: prediction
        ? provenanceLabel(prediction.source)
        : "Business signals engine",
      graphNodeId: signalId ? `prediction:${signalId}` : undefined,
      priorityEvidence,
      askPrompt: `Why does Gravitre think "${title}" needs attention?`,
    }
  }

  if (selection.kind === "department") {
    const dept = selection.department
    return {
      eyebrow: "Department",
      title: dept.id.replace(/_/g, " "),
      facts: [
        { label: "State", value: dept.state.replace(/-/g, " ") },
        { label: "Events in window", value: String(dept.eventsInWindow) },
        ...(dept.confidence != null
          ? [{ label: "Confidence", value: `${Math.round(dept.confidence * 100)}%` }]
          : []),
        { label: "Time window", value: `${windowHours}h` },
      ],
      evidence: [],
      qualityFlags: formatQualityFlags(pageContext?.qualityFlags ?? []),
      provenance: "Outcome events aggregation",
      graphNodeId: `dept:${dept.id}`,
      priorityEvidence: matchPriorityEvidence(whyData, { department: dept.id }),
      askPrompt: `What is happening in ${dept.id.replace(/_/g, " ")} right now?`,
    }
  }

  const node = selection.node
  const graphNode = findGraphNode(pageContext, node.id)

  if (node.kind === "learning") {
    const learningId = node.id.replace(/^learning:/, "")
    const insight = snapshot ? findCanonicalLearning(snapshot, learningId) : undefined
    return {
      eyebrow: "Business learning",
      title: insight ? readString(insight.businessStatement, node.label) : node.label,
      summary: node.sublabel,
      facts: [
        ...(insight?.learnedAt
          ? [{ label: "Learned", value: String(insight.learnedAt) }]
          : []),
        ...(insight?.confidence
          ? [{ label: "Confidence", value: String(insight.confidence) }]
          : []),
        { label: "Time window", value: `${windowHours}h` },
      ],
      evidence: (insight?.evidence as string[] | undefined) ?? [],
      qualityFlags: formatQualityFlags(pageContext?.qualityFlags ?? []),
      provenance: insight ? provenanceLabel(insight.source) : "Memory promotion",
      graphNodeId: node.id,
      askPrompt: `What evidence supports this learning: ${node.label}?`,
    }
  }

  if (node.kind === "model") {
    return {
      eyebrow: "Model",
      title: node.label,
      summary: node.sublabel,
      facts: [{ label: "Status", value: node.sublabel ?? "Unknown" }],
      evidence: [],
      qualityFlags: [],
      provenance: "Model catalog",
      graphNodeId: node.id,
      askPrompt: `How is the ${node.label} model performing?`,
    }
  }

  return {
    eyebrow: node.kind.replace("-", " "),
    title: node.label,
    summary: node.sublabel,
    facts: graphNode?.status
      ? [{ label: "Status", value: String(graphNode.status) }]
      : [],
    evidence: [],
    qualityFlags: formatQualityFlags(pageContext?.qualityFlags ?? []),
    provenance: graphNode ? provenanceLabel(graphNode.source) : undefined,
    graphNodeId: node.id,
    askPrompt: `Tell me more about ${node.label}.`,
  }
}
