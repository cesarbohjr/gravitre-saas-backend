/**
 * Gravitre department network — shared types for the signature converge animation.
 */

export type DepartmentId = "sales" | "support" | "operations" | "finance"

export type CoreState =
  | "idle"
  | "receiving"
  | "connecting"
  | "coordinating"
  | "acting"
  | "verifying"
  | "learning"
  | "verified"
  | "learned"

export type PacketKind = "signal" | "action" | "learn"

export type PathEndpoint = DepartmentId | "core"

export type StoryBeat =
  | { type: "activate"; dept: DepartmentId; caption?: string; durationMs?: number }
  | { type: "packet"; from: PathEndpoint; to: PathEndpoint; kind: PacketKind; caption?: string; durationMs?: number }
  | { type: "core"; state: CoreState; caption?: string; durationMs?: number }
  | { type: "resolve"; dept: DepartmentId; caption?: string; durationMs?: number }
  | { type: "settle"; caption?: string; durationMs?: number }

export type NetworkScenario = {
  id: string
  label: string
  source: DepartmentId
  beats: StoryBeat[]
}

/** CSS percentage positions inside the stage (keeps nodes fully in-frame). */
export const DEPARTMENT_META: Record<
  DepartmentId,
  { label: string; short: string; left: string; top: string }
> = {
  sales: { label: "Sales", short: "Sales", left: "8%", top: "10%" },
  support: { label: "Support", short: "Support", left: "92%", top: "10%" },
  operations: { label: "Operations", short: "Ops", left: "8%", top: "88%" },
  finance: { label: "Finance", short: "Finance", left: "92%", top: "88%" },
}

export const CORE_STATE_LABEL: Partial<Record<CoreState, string>> = {
  receiving: "Receiving",
  connecting: "Connecting context",
  coordinating: "Coordinating",
  acting: "Acting",
  verifying: "Verifying",
  learning: "Learning",
  verified: "Verified",
  learned: "Learned",
}

/** SVG viewBox — paths use the same percentage→pixel mapping */
export const NETWORK_VB = { w: 600, h: 420, cx: 300, cy: 210 } as const

/** Pixel anchors matching DEPARTMENT_META percentages */
export const DEPARTMENT_XY: Record<DepartmentId, { x: number; y: number }> = {
  sales: { x: 600 * 0.08, y: 420 * 0.1 },
  support: { x: 600 * 0.92, y: 420 * 0.1 },
  operations: { x: 600 * 0.08, y: 420 * 0.88 },
  finance: { x: 600 * 0.92, y: 420 * 0.88 },
}
