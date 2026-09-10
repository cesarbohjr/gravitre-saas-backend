import {
  Bot,
  Database,
  Headphones,
  Megaphone,
  PieChart,
  TrendingUp,
  Users,
  Mail,
  Calendar,
  Search,
  DollarSign,
  ShieldCheck,
  Workflow,
  Sparkles,
  HeartHandshake,
  Settings2,
  BarChart3,
  type LucideIcon,
} from "lucide-react"

/** Canonical API / UI department labels — aligned with fleet TEAM lanes. */
export type AgentDepartment =
  | "Marketing"
  | "Sales"
  | "Finance"
  | "Support"
  | "HR"
  | "Operations"
  | "Customer Success"
  | "Engineering"
  | "Security"
  | "General"

/** Select options for create / edit — matches fleet department order. */
export const AGENT_DEPARTMENT_OPTIONS: AgentDepartment[] = [
  "Sales",
  "Customer Success",
  "Finance",
  "Operations",
  "Engineering",
  "Marketing",
  "Security",
  "General",
]

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
  "Customer Success": {
    color: "cyan",
    gradient: "from-cyan-500 to-teal-500",
    glow: "shadow-cyan-500/30",
  },
  Engineering: { color: "teal", gradient: "from-teal-500 to-cyan-600", glow: "shadow-teal-500/30" },
  Security: { color: "slate", gradient: "from-slate-500 to-zinc-600", glow: "shadow-slate-500/30" },
  General: { color: "blue", gradient: "from-blue-500 to-indigo-500", glow: "shadow-blue-500/30" },
}

const EXACT_DEPARTMENT: Record<string, AgentDepartment> = {
  marketing: "Marketing",
  sales: "Sales",
  finance: "Finance",
  support: "Support",
  hr: "HR",
  operations: "Operations",
  "customer success": "Customer Success",
  customersuccess: "Customer Success",
  customer_success: "Customer Success",
  engineering: "Engineering",
  security: "Security",
  general: "General",
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
  if (text.includes("engineer") || text.includes("platform") || text.includes("sre")) {
    return "Engineering"
  }
  if (text.includes("secur") || text.includes("compliance") || text.includes("risk")) {
    return "Security"
  }
  if (
    text.includes("customer success") ||
    text.includes("success") ||
    text.includes("support") ||
    text.includes("customer")
  ) {
    return "Customer Success"
  }
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
  return PERSONALITY_BY_DEPARTMENT[department] ?? PERSONALITY_BY_DEPARTMENT.Operations
}

/**
 * Preserve fleet-aligned department labels. Legacy Support/HR remain valid;
 * unknown values fall back to Operations only after alias matching fails.
 */
export function normalizeAgentDepartment(value: string): AgentDepartment {
  const trimmed = String(value ?? "").trim()
  if (!trimmed) return "Operations"

  const lower = trimmed.toLowerCase()
  const spaced = lower.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim()
  const compact = spaced.replace(/\s+/g, "")

  if (EXACT_DEPARTMENT[lower]) return EXACT_DEPARTMENT[lower]
  if (EXACT_DEPARTMENT[spaced]) return EXACT_DEPARTMENT[spaced]
  if (EXACT_DEPARTMENT[compact]) return EXACT_DEPARTMENT[compact]

  if (spaced.includes("sale") || spaced.includes("revenue")) return "Sales"
  if (spaced.includes("market")) return "Marketing"
  if (spaced.includes("finance") || spaced.includes("account")) return "Finance"
  if (spaced.includes("engineer") || spaced.includes("platform") || spaced.includes("sre")) {
    return "Engineering"
  }
  if (spaced.includes("secur") || spaced.includes("compliance")) return "Security"
  if (
    spaced.includes("customer success") ||
    spaced.includes("success") ||
    spaced.includes("support") ||
    spaced.includes("customer")
  ) {
    return "Customer Success"
  }
  if (
    spaced.includes("human resource") ||
    spaced === "hr" ||
    spaced.includes("people") ||
    spaced.includes("talent") ||
    spaced.includes("recruit")
  ) {
    return "HR"
  }
  if (spaced.includes("ops") || spaced.includes("operation")) return "Operations"
  if (spaced === "general") return "General"

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

// Ordered most-specific -> most-general; the first keyword match wins. Specific
// task words (report, invoice, email) come first, then department/function
// words (marketing, sales, finance, support, hr). Generic words like
// "operations" and "workflow" sit LAST so that, e.g., "Sales Operations"
// resolves to the sales glyph rather than a generic operations gear.
export function resolveAgentRoleIcon(role: string, name = ""): LucideIcon {
  const text = `${role} ${name}`.toLowerCase()
  // Specific task / artifact words.
  if (text.includes("report") || text.includes("analytic") || text.includes("insight") || text.includes("dashboard"))
    return PieChart
  if (text.includes("revenue") || text.includes("pipeline") || text.includes("forecast")) return BarChart3
  if (text.includes("invoice") || text.includes("billing") || text.includes("payment")) return DollarSign
  if (text.includes("compliance") || text.includes("legal") || text.includes("security") || text.includes("risk"))
    return ShieldCheck
  if (text.includes("schedul") || text.includes("calendar") || text.includes("meeting")) return Calendar
  if (text.includes("research") || text.includes("discovery")) return Search
  if (text.includes("email") || text.includes("inbox")) return Mail
  if (text.includes("campaign") || text.includes("content") || text.includes("brand")) return Megaphone
  // Department / function words.
  if (text.includes("marketing")) return Megaphone
  if (text.includes("sales")) return TrendingUp
  if (text.includes("finance") || text.includes("accounting")) return DollarSign
  if (text.includes("support") || text.includes("customer") || text.includes("service")) return Headphones
  if (text.includes("hr") || text.includes("human resource") || text.includes("people") || text.includes("talent"))
    return Users
  if (text.includes("engagement") || text.includes("retention")) return HeartHandshake
  if (text.includes("data") || text.includes("quality")) return Database
  // Generic fallbacks (lowest priority).
  if (text.includes("workflow") || text.includes("automation") || text.includes("orchestrat")) return Workflow
  if (text.includes("operations") || text.includes("ops")) return Settings2
  if (text.includes("assistant") || text.includes("copilot")) return Sparkles
  return Bot
}
