/**
 * Phase 7 — Connector Fabric storyboard (illustrative, deterministic).
 * Capability ports — not a logo wall.
 */

export const ILLUSTRATIVE_CONTEXT =
  "A connector becomes usable when capabilities are authorized — not when a logo appears."

export const CAPABILITY_PORTS = [
  { id: "crm", label: "CRM", caps: ["READ", "WRITE"] as const },
  { id: "comms", label: "Comms", caps: ["READ", "SEND"] as const },
  { id: "finance", label: "Finance", caps: ["READ"] as const },
] as const

export type ConnectorPhase =
  | "quiet"
  | "ports"
  | "authorize"
  | "read"
  | "write_waiting"
  | "execute"
  | "evidence"
  | "honest"

export const PHASE_ORDER: ConnectorPhase[] = [
  "quiet",
  "ports",
  "authorize",
  "read",
  "write_waiting",
  "execute",
  "evidence",
  "honest",
]

export const PHASE_CAPTION: Record<ConnectorPhase, string> = {
  quiet: "No connector claims until capabilities are checked.",
  ports: "Capability ports appear — words for what the system can do.",
  authorize: "Auth and scopes gate every port before use.",
  read: "READ runs when authorized.",
  write_waiting: "WRITE pauses for approval — governance is part of the path.",
  execute: "After approval, the same write path continues.",
  evidence: "Evidence attaches to the connector action.",
  honest: "Not a live inventory of your stack. Logos are not proof of readiness.",
}

export function nextPhase(phase: ConnectorPhase): ConnectorPhase {
  const i = PHASE_ORDER.indexOf(phase)
  return PHASE_ORDER[(i + 1) % PHASE_ORDER.length] ?? "quiet"
}

export function isConnectorPhase(value: string | null | undefined): value is ConnectorPhase {
  if (!value) return false
  return (PHASE_ORDER as string[]).includes(value)
}

export function parseCfStateParam(
  raw: string | null | undefined,
  opts?: { hostname?: string | null },
): ConnectorPhase | null {
  if (!isConnectorPhase(raw)) return null
  const host = (opts?.hostname ?? "").toLowerCase()
  const local =
    host === "localhost" ||
    host === "127.0.0.1" ||
    host.endsWith(".localhost") ||
    process.env.NODE_ENV === "development"
  return local ? raw : null
}

export function showPorts(phase: ConnectorPhase): boolean {
  return phase !== "quiet"
}

export function showAuth(phase: ConnectorPhase): boolean {
  return !["quiet", "ports"].includes(phase)
}

export function writeWaiting(phase: ConnectorPhase): boolean {
  return phase === "write_waiting"
}

export function writeDone(phase: ConnectorPhase): boolean {
  return ["execute", "evidence", "honest"].includes(phase)
}

export function showEvidence(phase: ConnectorPhase): boolean {
  return ["evidence", "honest"].includes(phase)
}
