/**
 * Bridge legacy agent identity (Lucide ids + bg-*-500) → Agents 4.0 tiles.
 * API/DB continue to store legacy fields until a later migration.
 */

import type { AgentStatus } from "@/types/api"
import { suggestRoleIcon } from "@/components/agents/fleet-v4/identity-tokens"
import type {
  AgentDepartmentId,
  AgentIdentityColorId,
  AgentRoleIconId,
  AgentRuntimeState,
  FleetAgent,
} from "@/components/agents/fleet-v4/types"
import {
  isAgentAvatarColorId,
  isAgentIconId,
  resolveAgentIdentity,
  type AgentAvatarColorId,
  type AgentIconId,
  type AgentIdentity,
  type AgentIdentityInput,
} from "@/lib/agent-identity"

export const LEGACY_ICON_TO_ROLE: Record<AgentIconId, AgentRoleIconId> = {
  megaphone: "marketing",
  "trending-up": "sales",
  database: "data",
  "pie-chart": "finance",
  headphones: "support",
  bot: "general",
  brain: "knowledge",
  zap: "ops",
  users: "recruiting",
  shield: "security",
  sparkles: "general",
  workflow: "workflow",
}

export const LEGACY_COLOR_TO_IDENTITY: Record<AgentAvatarColorId, AgentIdentityColorId> = {
  "bg-emerald-500": "green",
  "bg-blue-500": "blue",
  "bg-amber-500": "amber",
  "bg-purple-500": "violet",
  "bg-rose-500": "rose",
  "bg-cyan-500": "cyan",
}

export const IDENTITY_COLOR_TO_LEGACY: Record<AgentIdentityColorId, AgentAvatarColorId> = {
  green: "bg-emerald-500",
  cyan: "bg-cyan-500",
  violet: "bg-purple-500",
  blue: "bg-blue-500",
  teal: "bg-cyan-500",
  amber: "bg-amber-500",
  rose: "bg-rose-500",
}

/** Near-term map: today's 4 API statuses → runtime vocabulary. */
export function agentStatusToRuntime(status: AgentStatus | string | null | undefined): AgentRuntimeState {
  switch (status) {
    case "processing":
      return "executing"
    case "error":
      return "failed"
    case "idle":
      return "idle"
    case "active":
      return "available"
    default:
      return "idle"
  }
}

export function mapApiDepartmentToFleet(
  department: string | null | undefined,
): { id: AgentDepartmentId; label: string } {
  const raw = String(department ?? "").trim()
  const key = raw.toLowerCase()
  if (key.includes("sale") || key.includes("revenue")) return { id: "sales", label: raw || "Sales" }
  if (key.includes("support") || key.includes("success") || key.includes("customer")) {
    return { id: "customer_success", label: raw || "Customer Success" }
  }
  if (key.includes("finance") || key.includes("account")) return { id: "finance", label: raw || "Finance" }
  if (key.includes("market")) return { id: "marketing", label: raw || "Marketing" }
  if (key.includes("secur") || key.includes("compliance")) return { id: "security", label: raw || "Security" }
  if (key.includes("engineer") || key.includes("platform") || key.includes("sre")) {
    return { id: "engineering", label: raw || "Engineering" }
  }
  if (key.includes("hr") || key.includes("people") || key.includes("talent") || key.includes("recruit")) {
    return { id: "general", label: raw || "HR" }
  }
  if (key === "general") return { id: "general", label: raw || "General" }
  if (key.includes("ops") || key.includes("operation")) return { id: "operations", label: raw || "Operations" }
  return { id: "operations", label: raw || "Operations" }
}

/** Persist fleet department id as a readable API/department label. */
export function mapFleetDepartmentToApi(department: AgentDepartmentId): string {
  const labels: Record<AgentDepartmentId, string> = {
    sales: "Sales",
    customer_success: "Customer Success",
    finance: "Finance",
    operations: "Operations",
    engineering: "Engineering",
    marketing: "Marketing",
    security: "Security",
    general: "General",
  }
  return labels[department] ?? "Operations"
}

/** Convert a production agent record into a fleet TEAM/LIST card model. */
export function toFleetAgent(input: {
  id: string
  name: string
  role?: string | null
  department?: string | null
  status?: AgentStatus | string | null
  icon?: string | null
  avatarColor?: string | null
  avatarUrl?: string | null
  model?: string | null
  lastAction?: string | null
  lastActionTime?: string | null
  stats?: {
    tasksToday?: number
    successRate?: number | null
    workflowsUsing?: number
  } | null
  capabilities?: string[] | null
  permissions?: string[] | null
  connectedSystems?: string[] | null
  workflowCount?: number | null
  parentAgentId?: string | null
  config?: Record<string, unknown> | null
}): FleetAgent {
  const identity = resolveAgentIdentity({
    name: input.name,
    role: input.role,
    department: input.department,
    icon: input.icon,
    avatarColor: input.avatarColor,
    avatarUrl: input.avatarUrl,
  })
  const dept = mapApiDepartmentToFleet(input.department)
  const runtimeState = agentStatusToRuntime(input.status)
  const tasksToday = Number(input.stats?.tasksToday ?? 0)
  const successRaw = input.stats?.successRate
  const successRate =
    successRaw == null || !Number.isFinite(Number(successRaw)) || tasksToday <= 0
      ? null
      : Number(successRaw)

  const currentActivity =
    runtimeState === "executing" || runtimeState === "failed"
      ? input.lastAction && input.lastAction !== "No activity yet" && input.lastAction !== "No recent activity"
        ? input.lastAction
        : runtimeState === "executing"
          ? "Working…"
          : null
      : null

  return {
    id: input.id,
    name: identity.name,
    role: String(input.role ?? "Operator"),
    department: dept.id,
    departmentLabel: dept.label,
    icon: legacyIconToRole(identity.icon, input.role, identity.name, input.department),
    identityColor: legacyColorToIdentity(identity.avatarColor),
    configState: "enabled",
    runtimeState,
    currentActivity,
    tasksToday,
    successRate,
    model: String(input.model ?? "").trim() || "—",
    lastActiveLabel: String(input.lastActionTime ?? "unknown"),
    tools: Array.isArray(input.permissions) ? input.permissions.slice(0, 6) : [],
    workflows: [],
    connectedSystems: Array.isArray(input.connectedSystems)
      ? input.connectedSystems.map(String)
      : Array.isArray(input.permissions)
        ? input.permissions.slice(0, 8)
        : [],
    workflowCount: Number(input.stats?.workflowsUsing ?? input.workflowCount ?? 0) || undefined,
    parentAgentId: input.parentAgentId ?? null,
  }
}

export function legacyIconToRole(
  icon: string | null | undefined,
  role?: string | null,
  name?: string | null,
  department?: string | null,
): AgentRoleIconId {
  if (isAgentIconId(icon)) {
    // Generic brain/bot → prefer role-based suggestion when text is specific.
    if (icon === "brain" || icon === "bot" || icon === "sparkles") {
      const suggested = suggestRoleIcon(role ?? "", name ?? "", department ?? "")
      if (suggested !== "general" && suggested !== "knowledge") return suggested
      if (icon === "brain" && suggested === "knowledge") return "knowledge"
    }
    return LEGACY_ICON_TO_ROLE[icon]
  }
  return suggestRoleIcon(role ?? "", name ?? "", department ?? "")
}

export function legacyColorToIdentity(
  color: string | null | undefined,
  fallback: AgentIdentityColorId = "violet",
): AgentIdentityColorId {
  if (isAgentAvatarColorId(color)) return LEGACY_COLOR_TO_IDENTITY[color]
  return fallback
}

export interface V4IdentityView {
  icon: AgentRoleIconId
  identityColor: AgentIdentityColorId
  avatarUrl: string | null
  name: string
  initials: string
  runtimeState?: AgentRuntimeState
}

export function resolveV4IdentityView(
  input: AgentIdentityInput & { status?: AgentStatus | string | null },
  resolved?: AgentIdentity,
): V4IdentityView {
  const identity = resolved ?? resolveAgentIdentity(input)
  return {
    icon: legacyIconToRole(identity.icon, input.role, identity.name, input.department),
    identityColor: legacyColorToIdentity(identity.avatarColor),
    avatarUrl: identity.avatarUrl,
    name: identity.name,
    initials: identity.initials,
    runtimeState: input.status != null ? agentStatusToRuntime(input.status) : undefined,
  }
}
