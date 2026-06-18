import {
  Robot,
  FlowArrow,
  BookOpen,
  Package,
  Headset,
  UsersThree,
  ChartLineUp,
  Wrench,
  Megaphone,
} from "@phosphor-icons/react"
import type { Icon } from "@phosphor-icons/react"

export type AssetCategory =
  | "ai_agent"
  | "workflow"
  | "knowledge_pack"
  | "department_pack"

export interface CategoryIconConfig {
  icon: Icon
  // Tailwind token classes only — never raw hex.
  chipBg: string // light mode chip background
  chipBgDark: string // dark mode chip background
  iconColor: string // duotone primary color class (light + dark)
}

// Base category icons — used when no more specific department match applies
// (e.g. an individual AI Agent or Workflow card that isn't a department pack).
// NOTE: `ai_agent` intentionally uses cyan, not blue, so it stays clearly
// distinct from the blue Revenue Operations department pack in the same grid.
export const CATEGORY_ICONS: Record<AssetCategory, CategoryIconConfig> = {
  ai_agent: {
    icon: Robot,
    chipBg: "bg-cyan-100",
    chipBgDark: "dark:bg-cyan-950/40",
    iconColor: "text-cyan-600 dark:text-cyan-400",
  },
  workflow: {
    icon: FlowArrow,
    chipBg: "bg-indigo-100",
    chipBgDark: "dark:bg-indigo-950/40",
    iconColor: "text-indigo-600 dark:text-indigo-400",
  },
  knowledge_pack: {
    icon: BookOpen,
    chipBg: "bg-slate-100",
    chipBgDark: "dark:bg-slate-800/60",
    iconColor: "text-slate-600 dark:text-slate-300",
  },
  department_pack: {
    icon: Package, // overridden per-department below when a match exists
    chipBg: "bg-gray-100",
    chipBgDark: "dark:bg-gray-800/60",
    iconColor: "text-gray-600 dark:text-gray-300",
  },
}

// Department-specific overrides for Department Pack cards — this is what makes
// the outcome cards instantly distinguishable at a glance.
export const DEPARTMENT_ICONS: Record<string, CategoryIconConfig> = {
  customer_success: {
    icon: Headset,
    chipBg: "bg-teal-100",
    chipBgDark: "dark:bg-teal-950/40",
    iconColor: "text-teal-600 dark:text-teal-400",
  },
  hr: {
    icon: UsersThree,
    chipBg: "bg-rose-100",
    chipBgDark: "dark:bg-rose-950/40",
    iconColor: "text-rose-600 dark:text-rose-400",
  },
  revenue_operations: {
    icon: ChartLineUp,
    chipBg: "bg-blue-100",
    chipBgDark: "dark:bg-blue-950/40",
    iconColor: "text-blue-600 dark:text-blue-400",
  },
  operations: {
    // MSP Operations Pack
    icon: Wrench,
    chipBg: "bg-amber-100",
    chipBgDark: "dark:bg-amber-950/40",
    iconColor: "text-amber-600 dark:text-amber-400",
  },
  marketing: {
    icon: Megaphone,
    chipBg: "bg-violet-100",
    chipBgDark: "dark:bg-violet-950/40",
    iconColor: "text-violet-600 dark:text-violet-400",
  },
}

// Common aliases so varied backend department strings still resolve correctly
// (e.g. "Customer Success", "CS", "RevOps", "MSP Operations").
const DEPARTMENT_ALIASES: Record<string, string> = {
  cs: "customer_success",
  customer_success: "customer_success",
  customersuccess: "customer_success",
  human_resources: "hr",
  people: "hr",
  hr_operations: "hr",
  revops: "revenue_operations",
  revenue: "revenue_operations",
  revenue_ops: "revenue_operations",
  sales_operations: "revenue_operations",
  msp: "operations",
  msp_operations: "operations",
  it_operations: "operations",
  ops: "operations",
  marketing_operations: "marketing",
  growth: "marketing",
}

/**
 * Resolves the correct icon config for a card. Department packs check
 * DEPARTMENT_ICONS first (matched against the asset's `department` field,
 * lowercased + underscored, then alias-normalized), falling back to the
 * generic department_pack config only if no specific department match exists.
 *
 * Adding a new department pack later requires only one new entry here — no
 * code change anywhere else. Likewise, swapping the Department Pack icons to a
 * purchased Streamline duotone set only touches the `icon:` fields in this
 * file; the chip component and cards stay unchanged.
 */
export function getCategoryIcon(
  assetType: AssetCategory,
  department?: string | null,
): CategoryIconConfig {
  if (assetType === "department_pack" && department) {
    const raw = department.toLowerCase().trim().replace(/\s+/g, "_")
    const key = DEPARTMENT_ALIASES[raw] ?? raw
    if (DEPARTMENT_ICONS[key]) return DEPARTMENT_ICONS[key]
  }
  return CATEGORY_ICONS[assetType] ?? CATEGORY_ICONS.department_pack
}
