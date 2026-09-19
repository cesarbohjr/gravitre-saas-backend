/**
 * Pilot 3 — Knowledge Fabric Entity Convergence storyboard (illustrative, deterministic).
 * Exact / normalized mention match only — not fuzzy person ER.
 */

export const ILLUSTRATIVE_CONTEXT =
  "Mentions of the same company arrive from CRM and email — they should resolve to one identity."

export type FabricMention = {
  id: string
  raw: string
  normalized: string
  /** Mentions that share entityKey converge on exact normalized match. */
  entityKey: string | null
  /** When true, this mention must never merge with another person-like mention. */
  fuzzyPersonDemo?: boolean
}

export const MENTIONS: FabricMention[] = [
  { id: "m1", raw: "Acme Corp", normalized: "acme corp", entityKey: "acme-corp" },
  { id: "m2", raw: "acme corp.", normalized: "acme corp", entityKey: "acme-corp" },
  { id: "m3", raw: "Sarah", normalized: "sarah", entityKey: null, fuzzyPersonDemo: true },
  { id: "m4", raw: "Sarah Smith", normalized: "sarah smith", entityKey: null, fuzzyPersonDemo: true },
]

export type FabricPhase =
  | "quiet"
  | "receive"
  | "normalize"
  | "match"
  | "reject_fuzzy"
  | "evidence"
  | "persist"
  | "distinct"

export const PHASE_ORDER: FabricPhase[] = [
  "quiet",
  "receive",
  "normalize",
  "match",
  "reject_fuzzy",
  "evidence",
  "persist",
  "distinct",
]

export const PHASE_CAPTION: Record<FabricPhase, string> = {
  quiet: "Knowledge Fabric at rest — mentions are not yet resolved.",
  receive: "Mentions arrive from connected systems.",
  normalize: "Each mention is normalized (trim, case, punctuation) before match.",
  match: "Exact normalized matches converge into one entity.",
  reject_fuzzy:
    "Sarah and Sarah Smith stay separate — this is not fuzzy person matching.",
  evidence: "Evidence attaches to the resolved identity — not silent confidence.",
  persist: "A fabric relationship remains for the exact match.",
  distinct: "Knowledge Fabric is not the org graph. Mentions ≠ departments.",
}

export function nextPhase(phase: FabricPhase): FabricPhase {
  const i = PHASE_ORDER.indexOf(phase)
  return PHASE_ORDER[(i + 1) % PHASE_ORDER.length] ?? "quiet"
}

export function isFabricPhase(value: string | null | undefined): value is FabricPhase {
  if (!value) return false
  return (PHASE_ORDER as string[]).includes(value)
}

/** Localhost-only freeze for Pilot 3 (`?kfState=`). */
export function parseKfStateParam(
  raw: string | null | undefined,
  opts?: { hostname?: string | null },
): FabricPhase | null {
  if (!isFabricPhase(raw)) return null
  const host = (opts?.hostname ?? "").toLowerCase()
  const local =
    host === "localhost" ||
    host === "127.0.0.1" ||
    host.endsWith(".localhost") ||
    process.env.NODE_ENV === "development"
  return local ? raw : null
}

export function convergingMentionIds(phase: FabricPhase): string[] {
  if (["match", "reject_fuzzy", "evidence", "persist", "distinct"].includes(phase)) {
    return ["m1", "m2"]
  }
  return []
}

export function showNormalized(phase: FabricPhase): boolean {
  return !["quiet", "receive"].includes(phase)
}

export function showFuzzyReject(phase: FabricPhase): boolean {
  return ["reject_fuzzy", "evidence", "persist", "distinct"].includes(phase)
}

export function showEvidence(phase: FabricPhase): boolean {
  return ["evidence", "persist", "distinct"].includes(phase)
}

export function showPersistEdge(phase: FabricPhase): boolean {
  return ["persist", "distinct"].includes(phase)
}

export function resolvedEntityLabel(phase: FabricPhase): string | null {
  if (convergingMentionIds(phase).length === 0) return null
  return "Acme Corp"
}
