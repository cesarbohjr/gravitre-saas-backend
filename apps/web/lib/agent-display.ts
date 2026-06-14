import {
  Bot,
  Database,
  Headphones,
  Megaphone,
  PieChart,
  TrendingUp,
  Users,
  type LucideIcon,
} from "lucide-react"

export type AgentDepartment =
  | "Marketing"
  | "Sales"
  | "Finance"
  | "Support"
  | "HR"
  | "Operations"

const PERSONALITY_BY_DEPARTMENT: Record<
  AgentDepartment,
  { color: string; gradient: string; glow: string }
> = {
  Marketing: { color: "pink", gradient: "from-pink-500 to-rose-500", glow: "shadow-pink-500/30" },
  Sales: { color: "emerald", gradient: "from-emerald-500 to-teal-500", glow: "shadow-emerald-500/30" },
  Finance: { color: "violet", gradient: "from-violet-500 to-purple-500", glow: "shadow-violet-500/30" },
  Support: { color: "cyan", gradient: "from-cyan-500 to-blue-500", glow: "shadow-cyan-500/30" },
  HR: { color: "amber", gradient: "from-amber-500 to-orange-500", glow: "shadow-amber-500/30" },
  Operations: { color: "blue", gradient: "from-blue-500 to-indigo-500", glow: "shadow-blue-500/30" },
}

export function inferAgentDepartment(
  name: string,
  purpose?: string | null,
  role?: string | null,
): AgentDepartment {
  const text = `${name} ${purpose ?? ""} ${role ?? ""}`.toLowerCase()
  if (text.includes("marketing")) return "Marketing"
  if (text.includes("sales")) return "Sales"
  if (text.includes("finance") || text.includes("accounting")) return "Finance"
  if (text.includes("support") || text.includes("customer")) return "Support"
  if (
    text.includes("hr") ||
    text.includes("human resource") ||
    text.includes("people ops") ||
    text.includes("talent")
  ) {
    return "HR"
  }
  return "Operations"
}

export function inferAgentPersonality(department: AgentDepartment) {
  return PERSONALITY_BY_DEPARTMENT[department]
}

export function normalizeAgentDepartment(value: string): AgentDepartment {
  if (
    value === "Marketing" ||
    value === "Sales" ||
    value === "Finance" ||
    value === "Support" ||
    value === "HR"
  ) {
    return value
  }
  return "Operations"
}

export function mapOperatorStatusToUi(status: string | null | undefined): string {
  const normalized = String(status ?? "").toLowerCase()
  if (normalized === "active") return "active"
  if (normalized === "processing" || normalized === "running") return "processing"
  if (normalized === "error" || normalized === "failed") return "error"
  return "idle"
}

export function mapAgentStatusToOperator(status: string | null | undefined): string {
  const normalized = String(status ?? "").toLowerCase()
  if (normalized === "active" || normalized === "processing") return "active"
  if (normalized === "draft" || normalized === "idle") return "draft"
  return "inactive"
}

export function resolveAgentRoleIcon(role: string, name = ""): LucideIcon {
  const text = `${role} ${name}`.toLowerCase()
  if (text.includes("marketing")) return Megaphone
  if (text.includes("sales")) return TrendingUp
  if (text.includes("data") || text.includes("quality")) return Database
  if (text.includes("finance") || text.includes("report")) return PieChart
  if (text.includes("support") || text.includes("customer")) return Headphones
  if (text.includes("hr") || text.includes("human resource") || text.includes("people")) return Users
  return Bot
}
