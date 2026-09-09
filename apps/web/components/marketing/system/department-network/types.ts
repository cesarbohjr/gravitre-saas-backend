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

export const DEPARTMENT_META: Record<DepartmentId, { label: string; short: string }> = {
  sales: { label: "Sales", short: "Sales" },
  support: { label: "Support", short: "Support" },
  operations: { label: "Operations", short: "Ops" },
  finance: { label: "Finance", short: "Finance" },
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

/**
 * SVG viewBox geometry.
 * Node anchors sit inset (~18%/82%) so cards never kiss the clip edge.
 */
export const NETWORK_VB = { w: 640, h: 480, cx: 320, cy: 240 } as const

export const DEPARTMENT_XY: Record<DepartmentId, { x: number; y: number }> = {
  sales: { x: 640 * 0.2, y: 480 * 0.2 },
  support: { x: 640 * 0.8, y: 480 * 0.2 },
  operations: { x: 640 * 0.2, y: 480 * 0.8 },
  finance: { x: 640 * 0.8, y: 480 * 0.8 },
}
