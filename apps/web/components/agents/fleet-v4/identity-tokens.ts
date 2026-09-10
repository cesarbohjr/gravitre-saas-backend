import type { ComponentType, SVGProps } from "react"
import {
  NucleoAgent,
  NucleoApproval,
  NucleoActivity,
  NucleoIntelligence,
  NucleoSearch,
  NucleoVoice,
  NucleoWorkflow,
} from "@/components/icons/nucleo/semantic"
import {
  NavChart,
  NavDatabase,
  NavTarget,
  NavTasks,
  NavSparkles,
} from "@/components/icons/nodus-nav/outline"
import type { AgentIdentityColorId, AgentRoleIconId, AgentDepartmentId } from "./types"

type IconComponent = ComponentType<SVGProps<SVGSVGElement> & { size?: number | string }>

/**
 * Solid Nodus tiles — crisp icon ink, no washed /90 surfaces.
 * Identity color ≠ status color.
 */
export const IDENTITY_COLOR_TOKENS: Record<
  AgentIdentityColorId,
  { label: string; surfaceClass: string; iconClass: string; borderClass: string }
> = {
  green: {
    label: "Green",
    surfaceClass: "bg-emerald-100 dark:bg-emerald-950/50",
    iconClass: "text-emerald-700 dark:text-emerald-200",
    borderClass: "border-emerald-300 dark:border-emerald-700",
  },
  cyan: {
    label: "Cyan",
    surfaceClass: "bg-cyan-100 dark:bg-cyan-950/50",
    iconClass: "text-cyan-700 dark:text-cyan-200",
    borderClass: "border-cyan-300 dark:border-cyan-700",
  },
  violet: {
    label: "Violet",
    surfaceClass: "bg-violet-100 dark:bg-violet-950/50",
    iconClass: "text-violet-700 dark:text-violet-200",
    borderClass: "border-violet-300 dark:border-violet-700",
  },
  blue: {
    label: "Blue",
    surfaceClass: "bg-sky-100 dark:bg-sky-950/50",
    iconClass: "text-sky-700 dark:text-sky-200",
    borderClass: "border-sky-300 dark:border-sky-700",
  },
  teal: {
    label: "Teal",
    surfaceClass: "bg-teal-100 dark:bg-teal-950/50",
    iconClass: "text-teal-700 dark:text-teal-200",
    borderClass: "border-teal-300 dark:border-teal-700",
  },
  amber: {
    label: "Amber",
    surfaceClass: "bg-amber-100 dark:bg-amber-950/45",
    iconClass: "text-amber-800 dark:text-amber-100",
    borderClass: "border-amber-300 dark:border-amber-700",
  },
  rose: {
    label: "Rose",
    surfaceClass: "bg-rose-100 dark:bg-rose-950/50",
    iconClass: "text-rose-700 dark:text-rose-200",
    borderClass: "border-rose-300 dark:border-rose-700",
  },
}

/**
 * Role → icon. Nucleo first; Nodus-nav fills sales/finance/analytics until
 * additional Nucleo Sharp glyphs are imported in Phase 1.
 */
export const ROLE_ICON_REGISTRY: Record<
  AgentRoleIconId,
  { label: string; category: string; Icon: IconComponent; source: "nucleo" | "nodus-nav" }
> = {
  sales: { label: "Sales", category: "Sales", Icon: NavTarget as IconComponent, source: "nodus-nav" },
  support: { label: "Support", category: "Support", Icon: NucleoVoice, source: "nucleo" },
  finance: { label: "Finance", category: "Finance", Icon: NavChart as IconComponent, source: "nodus-nav" },
  ops: { label: "Operations", category: "Operations", Icon: NucleoWorkflow, source: "nucleo" },
  research: { label: "Research", category: "Research", Icon: NucleoSearch, source: "nucleo" },
  analytics: { label: "Analytics", category: "Analytics", Icon: NavChart as IconComponent, source: "nodus-nav" },
  reliability: { label: "Reliability", category: "Engineering", Icon: NucleoActivity, source: "nucleo" },
  security: { label: "Security", category: "Security", Icon: NucleoApproval, source: "nucleo" },
  recruiting: { label: "Recruiting", category: "Recruiting", Icon: NavTasks as IconComponent, source: "nodus-nav" },
  marketing: { label: "Marketing", category: "Marketing", Icon: NavSparkles as IconComponent, source: "nodus-nav" },
  knowledge: { label: "Knowledge", category: "Knowledge", Icon: NucleoIntelligence, source: "nucleo" },
  workflow: { label: "Workflow", category: "Workflow", Icon: NucleoWorkflow, source: "nucleo" },
  data: { label: "Data", category: "Data", Icon: NavDatabase as IconComponent, source: "nodus-nav" },
  general: { label: "General AI", category: "General AI", Icon: NucleoAgent, source: "nucleo" },
}

export const DEPARTMENT_ACCENT: Record<
  AgentDepartmentId,
  { label: string; accentClass: string; colorHint: AgentIdentityColorId }
> = {
  sales: { label: "Sales", accentClass: "text-violet-700 dark:text-violet-300", colorHint: "violet" },
  customer_success: {
    label: "Customer Success",
    accentClass: "text-sky-700 dark:text-sky-300",
    colorHint: "blue",
  },
  finance: { label: "Finance", accentClass: "text-emerald-700 dark:text-emerald-300", colorHint: "green" },
  operations: { label: "Operations", accentClass: "text-cyan-700 dark:text-cyan-300", colorHint: "cyan" },
  engineering: { label: "Engineering", accentClass: "text-teal-700 dark:text-teal-300", colorHint: "teal" },
  marketing: { label: "Marketing", accentClass: "text-amber-800 dark:text-amber-200", colorHint: "amber" },
  security: { label: "Security", accentClass: "text-rose-700 dark:text-rose-300", colorHint: "rose" },
  general: { label: "General", accentClass: "text-[color:var(--g-text-muted)]", colorHint: "violet" },
}

/** Suggest icon from role / name text — brain/knowledge only when appropriate. */
export function suggestRoleIcon(role: string, name = "", department = ""): AgentRoleIconId {
  const text = `${role} ${name} ${department}`.toLowerCase()
  if (/secur|compliance|risk|vulnerab/.test(text)) return "security"
  if (/reliab|infra|platform|sre|uptime|pulse/.test(text)) return "reliability"
  if (/cash|finance|invoice|billing|forecast/.test(text)) return "finance"
  if (/enrich|pipeline|sales|lead|revenue|deal/.test(text)) return "sales"
  if (/churn|support|ticket|customer success|cs\b/.test(text)) return "support"
  if (/recruit|talent|hiring|people ops/.test(text)) return "recruiting"
  if (/market|campaign|content/.test(text)) return "marketing"
  if (/visib|analytic|insight|dashboard|report/.test(text)) return "analytics"
  if (/research|account research|investigate/.test(text)) return "research"
  if (/workflow|orchestr|meson/.test(text)) return "workflow"
  if (/data|crm|hubspot|database/.test(text)) return "data"
  if (/gibe|knowledge|reasoning|core ai|general intelligence/.test(text)) return "knowledge"
  if (/ops|operations|runbook/.test(text)) return "ops"
  return "general"
}
