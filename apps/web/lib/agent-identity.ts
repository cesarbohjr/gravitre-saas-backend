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
  normalizeAgentDepartment,
  resolveAgentRoleIcon,
} from "@/lib/agent-display"
import { departmentGradient } from "@/lib/department-gradient"
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

export function suggestAgentIcon(
  name: string,
  purpose?: string | null,
  role?: string | null,
  department?: string | null,
): AgentIconId {
  const text = `${name} ${purpose ?? ""} ${role ?? ""} ${department ?? ""}`.toLowerCase()
  // Most-specific task words first.
  if (text.includes("vulnerab") || text.includes("security") || text.includes("compliance") || text.includes("risk"))
    return "shield"
  if (text.includes("ticket") || text.includes("triage") || text.includes("support") || text.includes("customer"))
    return "headphones"
  if (text.includes("email") || text.includes("campaign") || text.includes("marketing") || text.includes("content"))
    return "megaphone"
  if (text.includes("sales") || text.includes("pipeline") || text.includes("revenue") || text.includes("deal"))
    return "trending-up"
  if (text.includes("people") || text.includes("hr") || text.includes("talent") || text.includes("engagement"))
    return "users"
  if (text.includes("invoice") || text.includes("billing") || text.includes("finance") || text.includes("accounting"))
    return "pie-chart"
  if (text.includes("macro") || text.includes("report") || text.includes("dashboard") || text.includes("insight"))
    return "pie-chart"
  if (text.includes("data") || text.includes("quality") || text.includes("database")) return "database"
  if (text.includes("workflow") || text.includes("orchestrat") || text.includes("automation")) return "workflow"
  if (text.includes("analy") || text.includes("research") || text.includes("executive")) return "brain"
  if (text.includes("assistant") || text.includes("copilot") || text.includes("spark")) return "sparkles"
  if (text.includes("ops") || text.includes("operations")) return "zap"
  return "bot"
}

function hashPickColor(seed: string): AgentAvatarColorId {
  let hash = 0
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash + seed.charCodeAt(i) * (i + 1)) % AGENT_AVATAR_COLOR_IDS.length
  }
  return AGENT_AVATAR_COLOR_IDS[hash] ?? "bg-emerald-500"
}

/** Department → curated avatar color (aligned with marketplace orb palette). */
export function suggestColorForDepartment(department?: string | null): AgentAvatarColorId | null {
  const key = String(department ?? "").toLowerCase()
  if (!key) return null
  if (key.includes("market")) return "bg-purple-500"
  if (key.includes("sales") || key.includes("revenue")) return "bg-blue-500"
  if (key.includes("finance") || key.includes("account")) return "bg-emerald-500"
  if (key.includes("support") || key.includes("success") || key.includes("customer")) return "bg-cyan-500"
  if (key.includes("hr") || key.includes("people") || key.includes("talent")) return "bg-rose-500"
  if (key.includes("ops") || key.includes("operation")) return "bg-amber-500"
  return null
}

export function suggestAgentColor(
  icon: AgentIconId,
  name?: string | null,
  department?: string | null,
): AgentAvatarColorId {
  const fromDepartment = suggestColorForDepartment(department)
  if (fromDepartment) return fromDepartment

  const mapping: Partial<Record<AgentIconId, AgentAvatarColorId>> = {
    megaphone: "bg-purple-500",
    "trending-up": "bg-blue-500",
    database: "bg-cyan-500",
    "pie-chart": "bg-emerald-500",
    headphones: "bg-cyan-500",
    bot: "bg-blue-500",
    brain: "bg-purple-500",
    zap: "bg-amber-500",
    users: "bg-rose-500",
    shield: "bg-amber-500",
    sparkles: "bg-emerald-500",
    workflow: "bg-blue-500",
  }
  const fromIcon = mapping[icon]
  if (icon === "bot" && name) return hashPickColor(name)
  return fromIcon ?? (name ? hashPickColor(name) : "bg-emerald-500")
}

/** Vivid circular-orb personality: stored color token, else department gradient. */
export function personalityForIdentity(
  avatarColor: AgentAvatarColorId,
  department?: string | null,
  stored?: Partial<AgentPersonality> | null,
  preferDepartmentGradient = false,
): AgentPersonality {
  const fromColor = personalityFromAvatarColor(avatarColor)
  if (!preferDepartmentGradient) {
    return {
      color: String(stored?.color ?? fromColor.color),
      gradient: String(stored?.gradient ?? fromColor.gradient),
      glow: String(stored?.glow ?? fromColor.glow),
    }
  }
  const dept = departmentGradient(department)
  return {
    color: String(stored?.color ?? fromColor.color),
    gradient: dept.gradient,
    glow: dept.glow,
  }
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
  const role = input.role ?? null
  const department = normalizeAgentDepartment(
    String(input.department ?? inferAgentDepartment(name, null, role)),
  )
  const suggestedIcon = suggestAgentIcon(name, null, role, department)
  const storedIcon = isAgentIconId(input.icon) ? input.icon : null
  // Treat generic stored "bot" as unset when name/role implies a specific icon.
  const effectiveIcon =
    storedIcon && !(storedIcon === "bot" && suggestedIcon !== "bot")
      ? storedIcon
      : suggestedIcon

  const storedColor = isAgentAvatarColorId(input.avatarColor) ? input.avatarColor : null
  const avatarColor = storedColor ?? suggestAgentColor(effectiveIcon, name, department)
  const preferDepartmentGradient = !storedColor
  const storedPersonality = input.personality ?? null

  const avatarUrlRaw = String(input.avatarUrl ?? "").trim()
  const avatarUrl = avatarUrlRaw.length > 0 ? avatarUrlRaw : null

  // When color isn't explicitly stored, prefer the vivid department orb gradient
  // (amber ops / rose HR / etc.) so the list matches the classic circular look.
  const personality = personalityForIdentity(
    avatarColor,
    department,
    storedPersonality,
    preferDepartmentGradient,
  )
  // If stored personality already has a non-generic gradient and color was stored, keep it.
  if (storedColor && storedPersonality?.gradient) {
    personality.gradient = String(storedPersonality.gradient)
    personality.glow = String(storedPersonality.glow ?? personality.glow)
    personality.color = String(storedPersonality.color ?? personality.color)
  }

  return {
    name,
    icon: effectiveIcon,
    storedIcon,
    avatarColor,
    avatarUrl,
    personality,
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
