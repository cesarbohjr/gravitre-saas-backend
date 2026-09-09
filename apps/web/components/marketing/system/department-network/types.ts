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

export const DEPARTMENT_META: Record<
  DepartmentId,
  { label: string; short: string; angle: number }
> = {
  sales: { label: "Sales", short: "Sales", angle: -135 },
  support: { label: "Support", short: "Support", angle: -45 },
  operations: { label: "Operations", short: "Ops", angle: 135 },
  finance: { label: "Finance", short: "Finance", angle: 45 },
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

/** ViewBox geometry for the desktop radial composition */
export const NETWORK_VB = { w: 640, h: 480, cx: 320, cy: 240 } as const
export const NODE_RADIUS = 168
