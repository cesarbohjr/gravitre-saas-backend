import {
  TrendingUp,
  BarChart3,
  Megaphone,
  Headphones,
  Landmark,
  Users,
  Settings2,
  HeartHandshake,
  Scale,
  Stethoscope,
  Layers,
  Building2,
  Cpu,
  Briefcase,
  type LucideIcon,
} from "lucide-react"

export type DepartmentTheme = {
  icon: LucideIcon
  /** CSS color value for solid accents (e.g. progress rings). */
  tint: string
  /** Tailwind text-color class for the icon. */
  ring: string
  /** Tailwind text-color class for emphasis text. */
  text: string
  /** Tailwind background class for the soft icon tile. */
  soft: string
}

// Brand-safe palette: cycles the four semantic accent tokens so every
// department reads as part of the same system while staying distinct.
const PRIMARY: Omit<DepartmentTheme, "icon"> = {
  tint: "var(--chart-1, var(--primary))",
  ring: "text-primary",
  text: "text-primary",
  soft: "bg-primary/10",
}
const SUCCESS: Omit<DepartmentTheme, "icon"> = {
  tint: "var(--chart-3, var(--success))",
  ring: "text-success",
  text: "text-success",
  soft: "bg-success/10",
}
const WARNING: Omit<DepartmentTheme, "icon"> = {
  tint: "var(--chart-2, var(--warning))",
  ring: "text-warning",
  text: "text-warning",
  soft: "bg-warning/10",
}
const INFO: Omit<DepartmentTheme, "icon"> = {
  tint: "var(--chart-4, var(--info))",
  ring: "text-info",
  text: "text-info",
  soft: "bg-info/10",
}

// Keyword rules are evaluated in order; the first match wins. Order matters:
// more specific phrases (e.g. "customer success", "revenue") must precede
// broader ones ("success"/"support", "operations").
const RULES: Array<{ match: string[]; icon: LucideIcon; color: Omit<DepartmentTheme, "icon"> }> = [
  { match: ["customer success", "customer-success", "success"], icon: HeartHandshake, color: SUCCESS },
  { match: ["revenue"], icon: BarChart3, color: INFO },
  { match: ["sales"], icon: TrendingUp, color: PRIMARY },
  { match: ["marketing", "growth", "demand"], icon: Megaphone, color: WARNING },
  { match: ["support", "service desk", "help", "msp", "service"], icon: Headphones, color: SUCCESS },
  { match: ["finance", "accounting", "billing"], icon: Landmark, color: PRIMARY },
  { match: ["hr", "human", "people", "talent", "recruit"], icon: Users, color: INFO },
  { match: ["legal", "compliance", "counsel"], icon: Scale, color: PRIMARY },
  { match: ["health", "clinical", "care", "medical"], icon: Stethoscope, color: INFO },
  { match: ["real estate", "real-estate", "property"], icon: Building2, color: WARNING },
  { match: ["engineering", "developer", "platform", "infra", "it"], icon: Cpu, color: INFO },
  { match: ["operations", "ops"], icon: Settings2, color: WARNING },
]

/**
 * Resolves a unique, on-brand icon + accent for a department string.
 * Matching is keyword-based so variants like "Revenue Operations",
 * "Customer Success", and "MSP Operations" each get a distinct icon.
 */
export function departmentTheme(department: string | null | undefined): DepartmentTheme {
  const key = (department ?? "").toLowerCase().trim()
  for (const rule of RULES) {
    if (rule.match.some((m) => key.includes(m))) {
      return { icon: rule.icon, ...rule.color }
    }
  }
  // Generic fallback (Platform/Operations-style) — still brand-tinted.
  return { icon: Layers, ...PRIMARY }
}

export { Briefcase }
