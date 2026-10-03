import type { ComponentType, SVGProps } from "react"
import {
  Activity,
  BookOpen,
  Bot,
  Calculator,
  ChartColumn,
  Combine,
  Database,
  Gauge,
  Headset,
  HeartHandshake,
  Megaphone,
  Repeat,
  ShieldCheck,
  SquareTerminal,
  Target,
  Telescope,
  UserSearch,
  Workflow,
} from "lucide-react"
import type { AgentIdentityColorId, AgentRoleIconId, AgentDepartmentId } from "./types"

type IconComponent = ComponentType<SVGProps<SVGSVGElement> & { size?: number | string; strokeWidth?: number | string }>

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
    surfaceClass: "bg-[color:var(--g-emerald-pale)] dark:bg-[color:color-mix(in_srgb,var(--g-emerald)_18%,transparent)]",
    iconClass: "text-[color:var(--g-emerald-deep)] dark:text-[color:var(--g-emerald-mint)]",
    borderClass: "border-[color:var(--g-emerald)]/35 dark:border-[color:var(--g-emerald)]/45",
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
    surfaceClass: "bg-[color:var(--ion-wash)] dark:bg-[color:color-mix(in_srgb,var(--g-electric)_16%,transparent)]",
    iconClass: "text-[color:var(--g-electric)] dark:text-[color:var(--ion-300)]",
    borderClass: "border-[color:var(--g-electric)]/30 dark:border-[color:var(--g-electric)]/40",
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
 * Canonical role → Lucide glyph. One glyph per role so a roster reads by
 * function; no sparkle, brain or wand as generic AI identity.
 */
export const ROLE_ICON_REGISTRY: Record<
  AgentRoleIconId,
  { label: string; category: string; Icon: IconComponent; source: "lucide" }
> = {
  sales: { label: "Sales", category: "Sales", Icon: Target, source: "lucide" },
  marketing: { label: "Marketing", category: "Marketing", Icon: Megaphone, source: "lucide" },
  support: { label: "Support", category: "Support", Icon: Headset, source: "lucide" },
  customer_success: { label: "Customer Success", category: "Customer Success", Icon: HeartHandshake, source: "lucide" },
  research: { label: "Research", category: "Research", Icon: Telescope, source: "lucide" },
  data: { label: "Data", category: "Data", Icon: Database, source: "lucide" },
  analytics: { label: "Analytics", category: "Analytics", Icon: ChartColumn, source: "lucide" },
  finance: { label: "Finance", category: "Finance", Icon: Calculator, source: "lucide" },
  ops: { label: "Operations", category: "Operations", Icon: Gauge, source: "lucide" },
  revops: { label: "RevOps", category: "Revenue Operations", Icon: Combine, source: "lucide" },
  security: { label: "Security", category: "Security", Icon: ShieldCheck, source: "lucide" },
  developer: { label: "Developer", category: "Engineering", Icon: SquareTerminal, source: "lucide" },
  reliability: { label: "Reliability", category: "Engineering", Icon: Activity, source: "lucide" },
  knowledge: { label: "Knowledge", category: "Knowledge", Icon: BookOpen, source: "lucide" },
  automation: { label: "Automation", category: "Automation", Icon: Repeat, source: "lucide" },
  workflow: { label: "Workflow", category: "Workflow", Icon: Workflow, source: "lucide" },
  recruiting: { label: "Recruiting", category: "People", Icon: UserSearch, source: "lucide" },
  general: { label: "General", category: "General", Icon: Bot, source: "lucide" },
}

export const DEPARTMENT_ACCENT: Record<
  AgentDepartmentId,
  { label: string; accentClass: string; colorHint: AgentIdentityColorId }
> = {
  sales: { label: "Sales", accentClass: "text-violet-700 dark:text-violet-300", colorHint: "violet" },
  customer_success: {
    label: "Customer Success",
    accentClass: "text-[color:var(--g-electric)]",
    colorHint: "blue",
  },
  finance: { label: "Finance", accentClass: "text-[color:var(--g-emerald-deep)]", colorHint: "green" },
  operations: { label: "Operations", accentClass: "text-cyan-700 dark:text-cyan-300", colorHint: "cyan" },
  engineering: { label: "Engineering", accentClass: "text-teal-700 dark:text-teal-300", colorHint: "teal" },
  marketing: { label: "Marketing", accentClass: "text-amber-800 dark:text-amber-200", colorHint: "amber" },
  security: { label: "Security", accentClass: "text-rose-700 dark:text-rose-300", colorHint: "rose" },
  general: { label: "General", accentClass: "text-[color:var(--g-text-muted)]", colorHint: "violet" },
}

/** Suggest icon from role / name text — function marks, not cartoon AI. */
export function suggestRoleIcon(role: string, name = "", department = ""): AgentRoleIconId {
  const text = `${role} ${name} ${department}`.toLowerCase()
  // Order matters: specific compound roles before the generic words they contain.
  if (/secur|compliance|risk|vulnerab|access review/.test(text)) return "security"
  if (/revops|revenue op|sales op|gtm op/.test(text)) return "revops"
  if (/customer success|churn|renewal|onboarding|\bcs\b/.test(text)) return "customer_success"
  if (/reliab|infra|platform|sre|uptime|pulse/.test(text)) return "reliability"
  if (/develop|engineer|code|devops|github|deploy/.test(text)) return "developer"
  if (/cash|finance|invoice|billing|forecast|accounting/.test(text)) return "finance"
  if (/research|investigat|competitive intel/.test(text)) return "research"
  if (/enrich|pipeline|sales|lead|deal|prospect/.test(text)) return "sales"
  if (/support|ticket|helpdesk|service desk/.test(text)) return "support"
  if (/recruit|talent|hiring|people ops|\bhr\b|human resource/.test(text)) return "recruiting"
  if (/market|campaign|content|seo/.test(text)) return "marketing"
  if (/visib|analytic|insight|dashboard|report/.test(text)) return "analytics"
  if (/automat|trigger|schedul/.test(text)) return "automation"
  if (/workflow|orchestr|meson/.test(text)) return "workflow"
  if (/data|crm|hubspot|database|quality/.test(text)) return "data"
  if (/gibe|knowledge|reasoning|core ai|general intelligence/.test(text)) return "knowledge"
  if (/ops|operations|runbook|\bmsp\b/.test(text)) return "ops"
  return "general"
}
