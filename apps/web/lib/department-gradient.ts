// Single source of truth for per-department orb colors. Shared by the Agents
// grid (lucide icons) and the Marketplace Department packs (phosphor icons) so
// both surfaces read as the same color language: one vivid gradient per
// department, applied to a glossy circular orb with a white glyph.
//
// Colors are deliberately aligned with the marketplace category palette
// (CS = teal, HR = rose, Revenue/Sales = blue, Ops = amber, Marketing = violet)
// so a department looks identical wherever it appears.

export type DepartmentGradient = {
  /** Tailwind `from-*`/`to-*` classes for the orb's `bg-gradient-to-br`. */
  gradient: string
  /** Tailwind shadow color class for the orb's colored glow. */
  glow: string
  /** Tailwind `border-*` class for hover/active states that need the department hue. */
  border: string
}

const TEAL: DepartmentGradient = { gradient: "from-teal-400 to-cyan-600", glow: "shadow-teal-500/30", border: "border-teal-500/60" }
const ROSE: DepartmentGradient = { gradient: "from-rose-400 to-pink-600", glow: "shadow-rose-500/30", border: "border-rose-500/60" }
const BLUE: DepartmentGradient = { gradient: "from-blue-400 to-indigo-600", glow: "shadow-blue-500/30", border: "border-blue-500/60" }
const AMBER: DepartmentGradient = { gradient: "from-amber-400 to-orange-600", glow: "shadow-amber-500/30", border: "border-amber-500/60" }
const VIOLET: DepartmentGradient = { gradient: "from-violet-400 to-fuchsia-600", glow: "shadow-violet-500/30", border: "border-violet-500/60" }
const EMERALD: DepartmentGradient = { gradient: "from-emerald-400 to-green-600", glow: "shadow-emerald-500/30", border: "border-emerald-500/60" }
const SLATE: DepartmentGradient = { gradient: "from-slate-400 to-slate-600", glow: "shadow-slate-500/30", border: "border-slate-500/60" }

// Canonical department key -> gradient.
const GRADIENTS: Record<string, DepartmentGradient> = {
  customer_success: TEAL,
  support: TEAL,
  hr: ROSE,
  revenue_operations: BLUE,
  sales: BLUE,
  finance: EMERALD,
  operations: AMBER,
  marketing: VIOLET,
  legal: SLATE,
  engineering: BLUE,
}

// Normalizes the many department strings the backend can emit (e.g. "Customer
// Success", "RevOps", "MSP Operations", "People Ops") to a canonical key.
const ALIASES: Record<string, string> = {
  cs: "customer_success",
  customersuccess: "customer_success",
  customer_success: "customer_success",
  human_resources: "hr",
  people: "hr",
  people_ops: "hr",
  talent: "hr",
  hr_operations: "hr",
  revops: "revenue_operations",
  revenue: "revenue_operations",
  revenue_ops: "revenue_operations",
  sales_operations: "revenue_operations",
  accounting: "finance",
  billing: "finance",
  msp: "operations",
  msp_operations: "operations",
  it_operations: "operations",
  it: "operations",
  ops: "operations",
  marketing_operations: "marketing",
  growth: "marketing",
  demand: "marketing",
  compliance: "legal",
  counsel: "legal",
  developer: "engineering",
  platform: "engineering",
  infra: "engineering",
}

/** Resolves the vivid gradient + glow for any department string. */
export function departmentGradient(department: string | null | undefined): DepartmentGradient {
  const raw = (department ?? "").toLowerCase().trim().replace(/\s+/g, "_")
  if (!raw) return BLUE
  const key = ALIASES[raw] ?? raw
  return GRADIENTS[key] ?? BLUE
}
