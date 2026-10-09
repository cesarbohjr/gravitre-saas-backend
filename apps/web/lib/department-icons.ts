/**
 * Department icons: every agent is drawn with its department's icon, in the
 * department's hue (--dept-* tokens in app/globals.css). One map so the
 * roster, chat, approvals, goals, workflows and pickers all agree.
 */
import {
  Bot,
  Calculator,
  Gauge,
  HeartHandshake,
  Megaphone,
  ShieldCheck,
  SquareTerminal,
  Target,
  type LucideIcon,
} from "lucide-react"
import { mapApiDepartmentToFleet } from "@/lib/agent-identity-bridge"
import type { AgentDepartmentId, AgentRoleIconId } from "@/components/agents/fleet-v4/types"

export const DEPARTMENT_ICONS: Record<AgentDepartmentId, LucideIcon> = {
  sales: Target,
  marketing: Megaphone,
  customer_success: HeartHandshake,
  operations: Gauge,
  finance: Calculator,
  engineering: SquareTerminal,
  security: ShieldCheck,
  general: Bot,
}

/** The role glyph that matches each department, for surfaces keyed by role icon. */
export const DEPARTMENT_ROLE_ICON: Record<AgentDepartmentId, AgentRoleIconId> = {
  sales: "sales",
  marketing: "marketing",
  customer_success: "customer_success",
  operations: "ops",
  finance: "finance",
  engineering: "developer",
  security: "security",
  general: "general",
}

/** Department a role glyph belongs to, for steps that only know a role or a name. */
export const ROLE_DEPARTMENT: Record<AgentRoleIconId, AgentDepartmentId> = {
  sales: "sales",
  revops: "sales",
  marketing: "marketing",
  support: "customer_success",
  customer_success: "customer_success",
  finance: "finance",
  ops: "operations",
  automation: "operations",
  workflow: "operations",
  data: "operations",
  analytics: "operations",
  research: "general",
  knowledge: "general",
  security: "security",
  developer: "engineering",
  reliability: "engineering",
  recruiting: "general",
  general: "general",
}

const DEPARTMENT_IDS = new Set<string>(Object.keys(DEPARTMENT_ICONS))

/**
 * Resolve an API label ("Customer Success", "Support"), a fleet id
 * ("customer_success") or nothing to a department id. A missing department
 * reads as General rather than guessing a team.
 */
export function departmentIdFor(department: string | null | undefined): AgentDepartmentId {
  const raw = String(department ?? "").trim()
  if (!raw) return "general"
  if (DEPARTMENT_IDS.has(raw)) return raw as AgentDepartmentId
  return mapApiDepartmentToFleet(raw).id
}

export function departmentIconFor(department: string | null | undefined): LucideIcon {
  return DEPARTMENT_ICONS[departmentIdFor(department)]
}
