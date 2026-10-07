/**
 * Plain view model for the Knowledge › Memory review queue and inspector,
 * built only from memory-promotion candidates, audit rows and the agent list.
 * Nothing here invents a value: a missing field stays null and renders "—".
 */
import type { AutoPromotionRecord, PromotionCandidate } from "@/lib/api"
import { plainDecisionReasoning, readNumber } from "@/lib/intelligence/helpers"

export type MemoryQueueFilter = "pending" | "auto" | "rejected"

export type MemorySourceRow = {
  label: string
  role: "source" | "observed" | "decided"
}

export type MemoryItem = {
  key: string
  kind: MemoryQueueFilter | "example"
  candidateId: string | null
  memoryId: string | null
  content: string
  frequency: number | null
  departments: string[]
  departmentCount: number | null
  /** 0–1, only when the source row carries a real score. */
  confidence: number | null
  linksTo: string | null
  sources: MemorySourceRow[]
  /** Why this was remembered / what approving it does. */
  note: string | null
  minOccurrences: number | null
  minDepartments: number | null
  updatedAt: string | null
}

/** The backend's real status for "waiting for a person". */
export const PENDING_STATUS = "pending_approval"

const SOURCE_LABELS: Record<string, string> = {
  org_glossary_terms: "Business glossary",
  workflow_pattern: "Workflow runs",
  successful_response: "Answers people marked helpful",
  outcome_pattern: "Measured outcomes",
  decision_pattern: "Approval decisions",
  agent_memories: "Agent memory",
}

export function memorySourceLabel(sourceTable: unknown): string {
  const raw = String(sourceTable ?? "").trim()
  if (!raw) return "Unknown source"
  return SOURCE_LABELS[raw] ?? raw.replace(/^v4:/, "").replace(/[_:]+/g, " ").replace(/^\w/, (c) => c.toUpperCase())
}

function readRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {}
}

function readStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((v) => String(v ?? "").trim()).filter(Boolean) : []
}

/** Normalise a 0–1 or 0–100 score; anything else is "no score". */
export function normaliseConfidence(value: unknown): number | null {
  const n = readNumber(value, null)
  if (n == null || n < 0) return null
  if (n <= 1) return n
  if (n <= 100) return n / 100
  return null
}

function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`
}

export function candidateToMemoryItem(
  candidate: PromotionCandidate,
  kind: MemoryQueueFilter,
  agentNames: Record<string, string>,
): MemoryItem {
  const meta = readRecord(candidate.metadata)
  const departments = readStringList(meta.departments)
  const frequency = readNumber(candidate.frequency, null)
  const departmentCount = readNumber(candidate.department_count, null)
  const agentId = meta.agent_id ? String(meta.agent_id) : null
  const agentName = agentId ? agentNames[agentId] ?? null : null
  const sampleSize = readNumber(meta.sample_size, null)

  const sources: MemorySourceRow[] = [{ label: memorySourceLabel(candidate.source_table), role: "source" }]
  if (agentName) {
    sources.push({ label: sampleSize != null ? `${agentName} · ${plural(sampleSize, "run")}` : agentName, role: "observed" })
  }
  for (const dept of departments) sources.push({ label: `${dept} team`, role: "observed" })
  if (!agentName && departments.length === 0 && frequency != null && frequency > 0) {
    sources.push({ label: `Seen ${plural(frequency, "time")}`, role: "observed" })
  }

  const term = typeof meta.term === "string" && meta.term.trim() ? meta.term.trim() : null
  const tc = candidate.thresholdComparison
  const reasoning =
    typeof meta.reasoning === "string" && meta.reasoning.trim()
      ? plainDecisionReasoning(meta.reasoning)
      : typeof meta.decision_reasoning === "string" && meta.decision_reasoning.trim()
        ? plainDecisionReasoning(meta.decision_reasoning)
        : null

  return {
    key: `${kind}:${candidate.id}`,
    kind,
    candidateId: candidate.id,
    memoryId: Array.isArray(candidate.memory_ids) && candidate.memory_ids[0] ? String(candidate.memory_ids[0]) : null,
    content: String(candidate.content ?? "").trim() || "—",
    frequency,
    departments,
    departmentCount,
    confidence: normaliseConfidence(meta.confidence ?? meta.win_rate),
    linksTo: term ?? agentName,
    sources,
    note: reasoning,
    minOccurrences: tc ? readNumber(tc.autoPromoteMinOccurrences, null) : null,
    minDepartments: tc ? readNumber(tc.autoPromoteMinDepartments, null) : null,
    updatedAt: candidate.updated_at ?? null,
  }
}

export function autoPromotionToMemoryItem(
  record: AutoPromotionRecord,
  index: number,
  candidatesById: Record<string, PromotionCandidate>,
  agentNames: Record<string, string>,
): MemoryItem {
  const candidate = record.candidate_id ? candidatesById[String(record.candidate_id)] : undefined
  const base = candidate ? candidateToMemoryItem(candidate, "auto", agentNames) : null
  const snapshot = readRecord(record.thresholdSnapshot ?? record.threshold_snapshot)
  const reasoning = plainDecisionReasoning(record.decisionReasoning ?? record.decision_reasoning)
  const memoryId = record.memory_id ? String(record.memory_id) : null
  return {
    key: `auto:${memoryId ?? record.candidate_id ?? index}`,
    kind: "auto",
    candidateId: record.candidate_id ? String(record.candidate_id) : null,
    memoryId,
    content: base?.content ?? (typeof snapshot.term === "string" ? snapshot.term : reasoning),
    frequency: base?.frequency ?? readNumber(snapshot.frequency, null),
    departments: base?.departments ?? [],
    departmentCount: base?.departmentCount ?? readNumber(snapshot.department_count, null),
    confidence: base?.confidence ?? null,
    linksTo: base?.linksTo ?? (typeof snapshot.term === "string" ? snapshot.term : null),
    sources: [
      ...(base?.sources ?? [{ label: memorySourceLabel(record.source_table), role: "source" as const }]),
      { label: "Shared automatically", role: "decided" as const },
    ],
    note: reasoning,
    minOccurrences: base?.minOccurrences ?? readNumber(snapshot.min_occurrences, null),
    minDepartments: base?.minDepartments ?? readNumber(snapshot.min_departments, null),
    updatedAt: record.decided_at ?? base?.updatedAt ?? null,
  }
}

/** Design-labelled example, shown only when "Preview with an example memory" is on. */
export const EXAMPLE_MEMORY: MemoryItem = {
  key: "example",
  kind: "example",
  candidateId: null,
  memoryId: null,
  content: "Refrigerated freight only ships from the Reno and Tacoma depots.",
  frequency: 4,
  departments: [],
  departmentCount: null,
  confidence: 0.86,
  linksTo: "Depot",
  sources: [
    { label: "Postgres warehouse · shipments table", role: "source" },
    { label: "Ticket triage agent · 3 runs", role: "observed" },
    { label: "Churn risk scorer · 1 run", role: "observed" },
  ],
  note: "If approved, agents will stop routing cold-chain tickets to the Fresno depot. That affected 2 of the last 40 tickets.",
  minOccurrences: null,
  minDepartments: null,
  updatedAt: null,
}

/** Scope shown in the inspector: who an approval writes this memory for. */
export function memoryScopeLabel(item: MemoryItem): string {
  if (item.kind === "example") return "Whole org"
  if (item.departments.length === 1) return `${item.departments[0]} team`
  if (item.departments.length > 1) return plural(item.departments.length, "team")
  if (item.departmentCount != null && item.departmentCount > 0) return plural(item.departmentCount, "team")
  return "Not set"
}

export function seenLabel(item: MemoryItem): string | null {
  if (item.frequency == null) return null
  if (item.kind === "example") return `Seen in ${plural(item.frequency, "run")}`
  return `Seen ${plural(item.frequency, "time")}`
}
