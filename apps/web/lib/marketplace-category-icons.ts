import { BookOpen, Package, Workflow, type LucideIcon } from "lucide-react"
import { ROLE_ICON_REGISTRY, suggestRoleIcon } from "@/components/agents/fleet-v4/identity-tokens"

export type AssetCategory =
  | "ai_agent"
  | "workflow"
  | "knowledge_pack"
  | "department_pack"

export interface CategoryIconConfig {
  icon: LucideIcon
  /** Accessible name of the glyph (role or asset kind). */
  label: string
}

/**
 * One glyph language for marketplace assets: Lucide only, no tile colour.
 * Agents and department packs read by role (same registry as the Agents
 * roster); workflows and knowledge keep their kind glyph.
 */
export function getCategoryIcon(
  assetType: AssetCategory | string,
  department?: string | null,
  title = "",
): CategoryIconConfig {
  if (assetType === "workflow") return { icon: Workflow, label: "Workflow" }
  if (assetType === "knowledge_pack") return { icon: BookOpen, label: "Knowledge" }
  if (assetType === "ai_agent" || assetType === "department_pack") {
    const dept = (department ?? "").replace(/_/g, " ")
    const roleId = suggestRoleIcon("", title, dept)
    if (roleId === "general" && assetType === "department_pack") return { icon: Package, label: "Department pack" }
    const entry = ROLE_ICON_REGISTRY[roleId]
    return { icon: entry.Icon as LucideIcon, label: entry.label }
  }
  return { icon: Package, label: "Pack" }
}
