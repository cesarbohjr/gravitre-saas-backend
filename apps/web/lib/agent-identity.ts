import {
  Bot,
  Brain,
  Database,
  Headphones,
  Megaphone,
  PieChart,
  Shield,
  Sparkles,
  TrendingUp,
  Users,
  Workflow,
  Zap,
  type LucideIcon,
} from "lucide-react"
import {
  inferAgentDepartment,
  inferAgentPersonality,
  normalizeAgentDepartment,
  resolveAgentRoleIcon,
  type AgentDepartment,
} from "@/lib/agent-display"
import type { AgentPersonality } from "@/types/api"

/** Curated icon ids — must match backend VALID_AGENT_ICONS. */
export const AGENT_ICON_IDS = [
  "megaphone",
  "trending-up",
  "database",
  "pie-chart",
  "headphones",
  "bot",
  "brain",
  "zap",
  "users",
  "shield",
  "sparkles",
  "workflow",
] as const

export type AgentIconId = (typeof AGENT_ICON_IDS)[number]

/** Curated avatar colors — must match backend VALID_AVATAR_COLORS. */
export const AGENT_AVATAR_COLOR_IDS = [
  "bg-emerald-500",
  "bg-blue-500",
  "bg-amber-500",
  "bg-purple-500",
  "bg-rose-500",
  "bg-cyan-500",
] as const

export type AgentAvatarColorId = (typeof AGENT_AVATAR_COLOR_IDS)[number]

export const AGENT_ICON_OPTIONS: Array<{ id: AgentIconId; label: string }> = [
  { id: "megaphone", label: "Marketing" },
  { id: "trending-up", label: "Sales" },
  { id: "database", label: "Data" },
  { id: "pie-chart", label: "Reports" },
  { id: "headphones", label: "Support" },
  { id: "bot", label: "General" },
  { id: "brain", label: "Analysis" },
  { id: "zap", label: "Automation" },
  { id: "users", label: "People" },
  { id: "shield", label: "Security" },
  { id: "sparkles", label: "Assistant" },
  { id: "workflow", label: "Workflow" },
]

export const AGENT_COLOR_OPTIONS: Array<{ id: AgentAvatarColorId; label: string; swatchClass: string }> = [
  { id: "bg-emerald-500", label: "Emerald", swatchClass: "bg-emerald-500" },
  { id: "bg-blue-500", label: "Blue", swatchClass: "bg-blue-500" },
  { id: "bg-amber-500", label: "Amber", swatchClass: "bg-amber-500" },
  { id: "bg-purple-500", label: "Purple", swatchClass: "bg-purple-500" },
  { id: "bg-rose-500", label: "Rose", swatchClass: "bg-rose-500" },
  { id: "bg-cyan-500", label: "Cyan", swatchClass: "bg-cyan-500" },
]

const ICON_COMPONENTS: Record<AgentIconId, LucideIcon> = {
  megaphone: Megaphone,
  "trending-up": TrendingUp,
  database: Database,
  "pie-chart": PieChart,
  headphones: Headphones,
  bot: Bot,
  brain: Brain,
  zap: Zap,
  users: Users,
  shield: Shield,
  sparkles: Sparkles,
  workflow: Workflow,
}

const COLOR_GRADIENTS: Record<AgentAvatarColorId, AgentPersonality> = {
  "bg-emerald-500": {
    color: "emerald",
    gradient: "from-emerald-500 to-teal-600",
    glow: "shadow-emerald-500/30",
  },
  "bg-blue-500": {
    color: "blue",
    gradient: "from-blue-500 to-indigo-600",
    glow: "shadow-blue-500/30",
  },
  "bg-amber-500": {
    color: "amber",
    gradient: "from-amber-500 to-orange-600",
    glow: "shadow-amber-500/30",
  },
  "bg-purple-500": {
    color: "purple",
    gradient: "from-purple-500 to-violet-600",
    glow: "shadow-purple-500/30",
  },
  "bg-rose-500": {
    color: "rose",
    gradient: "from-rose-500 to-pink-600",
    glow: "shadow-rose-500/30",
  },
  "bg-cyan-500": {
    color: "cyan",
    gradient: "from-cyan-500 to-blue-600",
    glow: "shadow-cyan-500/30",
  },
}

export interface AgentIdentity {
  name: string
  /** Effective icon for rendering (stored value or suggested fallback). */
  icon: AgentIconId
  /** Raw stored icon from the database, if any. */
  storedIcon: AgentIconId | null
  avatarColor: AgentAvatarColorId
  avatarUrl: string | null
  personality: AgentPersonality
  initials: string
}

export interface AgentIdentityInput {
  name?: string | null
  role?: string | null
  department?: string | null
  icon?: string | null
  avatarColor?: string | null
  avatarUrl?: string | null
  personality?: Partial<AgentPersonality> | null
}

export function isAgentIconId(value: string | null | undefined): value is AgentIconId {
  return Boolean(value && AGENT_ICON_IDS.includes(value as AgentIconId))
}

export function isAgentAvatarColorId(value: string | null | undefined): value is AgentAvatarColorId {
  return Boolean(value && AGENT_AVATAR_COLOR_IDS.includes(value as AgentAvatarColorId))
}

export function agentInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return "AG"
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0] ?? ""}${parts[1][0] ?? ""}`.toUpperCase()
}

export function personalityFromAvatarColor(color: AgentAvatarColorId): AgentPersonality {
  return COLOR_GRADIENTS[color]
}

export function resolveAgentIconComponent(
  icon: string | null | undefined,
  role?: string | null,
  name?: string | null,
): LucideIcon {
  if (isAgentIconId(icon)) {
    return ICON_COMPONENTS[icon]
  }
  return resolveAgentRoleIcon(role ?? "", name ?? "")
}

export function suggestAgentIcon(name: string, purpose?: string | null): AgentIconId {
  const text = `${name} ${purpose ?? ""}`.toLowerCase()
  if (text.includes("marketing") || text.includes("campaign")) return "megaphone"
  if (text.includes("sales") || text.includes("pipeline")) return "trending-up"
  if (text.includes("data") || text.includes("quality")) return "database"
  if (text.includes("finance") || text.includes("report")) return "pie-chart"
  if (text.includes("support") || text.includes("customer")) return "headphones"
  if (text.includes("security") || text.includes("compliance")) return "shield"
  if (text.includes("workflow") || text.includes("automation")) return "workflow"
  if (text.includes("people") || text.includes("hr") || text.includes("talent")) return "users"
  if (text.includes("analy") || text.includes("research")) return "brain"
  if (text.includes("assistant") || text.includes("copilot")) return "sparkles"
  return "bot"
}

export function suggestAgentColor(icon: AgentIconId): AgentAvatarColorId {
  const mapping: Partial<Record<AgentIconId, AgentAvatarColorId>> = {
    megaphone: "bg-emerald-500",
    "trending-up": "bg-blue-500",
    database: "bg-cyan-500",
    "pie-chart": "bg-purple-500",
    headphones: "bg-amber-500",
    bot: "bg-blue-500",
    brain: "bg-purple-500",
    zap: "bg-amber-500",
    users: "bg-rose-500",
    shield: "bg-emerald-500",
    sparkles: "bg-emerald-500",
    workflow: "bg-cyan-500",
  }
  return mapping[icon] ?? "bg-emerald-500"
}

export function defaultAvatarColorForRole(role?: string | null): AgentAvatarColorId {
  const mapping: Record<string, AgentAvatarColorId> = {
    Orchestrator: "bg-emerald-500",
    Executor: "bg-blue-500",
    Analyst: "bg-purple-500",
    QA: "bg-amber-500",
    Router: "bg-cyan-500",
  }
  return mapping[role?.trim() ?? ""] ?? "bg-emerald-500"
}

export function resolveAgentIdentity(input: AgentIdentityInput): AgentIdentity {
  const name = String(input.name ?? "Agent").trim() || "Agent"
  const department = normalizeAgentDepartment(String(input.department ?? inferAgentDepartment(name, null, input.role)))
  const storedIcon = isAgentIconId(input.icon) ? input.icon : null
  const effectiveIcon = storedIcon ?? suggestAgentIcon(name, null)
  const avatarColor =
    (isAgentAvatarColorId(input.avatarColor) ? input.avatarColor : null) ??
    suggestAgentColor(effectiveIcon)

  const fromColor = personalityFromAvatarColor(avatarColor)
  const fromDepartment = inferAgentPersonality(department as AgentDepartment)
  const storedPersonality = input.personality ?? {}

  const avatarUrlRaw = String(input.avatarUrl ?? "").trim()
  const avatarUrl = avatarUrlRaw.length > 0 ? avatarUrlRaw : null

  return {
    name,
    icon: effectiveIcon,
    storedIcon,
    avatarColor,
    avatarUrl,
    personality: {
      color: String(storedPersonality.color ?? fromColor.color ?? fromDepartment.color),
      gradient: String(storedPersonality.gradient ?? fromColor.gradient ?? fromDepartment.gradient),
      glow: String(storedPersonality.glow ?? fromColor.glow ?? fromDepartment.glow),
    },
    initials: agentInitials(name),
  }
}

export function coerceAgentIcon(value: string | null | undefined, fallback: AgentIconId): AgentIconId {
  return isAgentIconId(value) ? value : fallback
}

export function coerceAgentColor(value: string | null | undefined, fallback: AgentAvatarColorId): AgentAvatarColorId {
  return isAgentAvatarColorId(value) ? value : fallback
}

export function resolveAgentIdentityFromRecord(record: Record<string, unknown>): AgentIdentity {
  const personality =
    record.personality && typeof record.personality === "object"
      ? (record.personality as Partial<AgentPersonality>)
      : null

  return resolveAgentIdentity({
    name: String(record.name ?? "Agent"),
    role: String(record.role ?? ""),
    department: String(record.department ?? ""),
    icon: String(record.icon ?? record.icon_name ?? "") || null,
    avatarColor: String(record.avatarColor ?? record.avatar_color ?? "") || null,
    avatarUrl: String(record.avatarUrl ?? record.avatar_url ?? "") || null,
    personality,
  })
}
