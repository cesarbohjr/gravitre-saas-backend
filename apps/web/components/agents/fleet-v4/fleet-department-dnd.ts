/**
 * HTML5 drag payload for moving agents between department teams.
 */

import type { AgentDepartmentId } from "./types"

export const FLEET_AGENT_DRAG_MIME = "application/x-gravitre-fleet-agent"

export type FleetAgentDragPayload = {
  agentId: string
  fromDepartment: AgentDepartmentId
}

export function setFleetAgentDragData(
  dataTransfer: DataTransfer,
  payload: FleetAgentDragPayload,
): void {
  const raw = JSON.stringify(payload)
  dataTransfer.setData(FLEET_AGENT_DRAG_MIME, raw)
  dataTransfer.setData("text/plain", payload.agentId)
  dataTransfer.effectAllowed = "move"
}

export function getFleetAgentDragData(dataTransfer: DataTransfer): FleetAgentDragPayload | null {
  const typed = dataTransfer.getData(FLEET_AGENT_DRAG_MIME)
  if (typed) {
    try {
      const parsed = JSON.parse(typed) as FleetAgentDragPayload
      if (parsed?.agentId && parsed?.fromDepartment) return parsed
    } catch {
      /* ignore */
    }
  }
  const plain = dataTransfer.getData("text/plain")?.trim()
  if (!plain) return null
  return { agentId: plain, fromDepartment: "general" }
}

export const FLEET_DEPARTMENT_ORDER: AgentDepartmentId[] = [
  "sales",
  "customer_success",
  "finance",
  "operations",
  "engineering",
  "marketing",
  "security",
  "general",
]
