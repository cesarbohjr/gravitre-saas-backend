import {
  Activity,
  BookOpen,
  Bot,
  Code,
  CreditCard,
  Database,
  Rocket,
  Shield,
  Sparkles,
  Workflow,
  type LucideIcon,
} from "lucide-react"

/**
 * Single source of truth for the icon shown next to each docs category.
 * Used by the docs landing page and the sidebar so the iconography stays
 * consistent across the docs surface. Falls back to BookOpen.
 */
const CATEGORY_ICONS: Record<string, LucideIcon> = {
  "Getting Started": Rocket,
  "Core Concepts": BookOpen,
  Concepts: BookOpen,
  "How-to Guides": Bot,
  Guides: Bot,
  "AI Operator": Sparkles,
  Workflows: Workflow,
  "API Reference": Code,
  API: Code,
  Security: Shield,
  Integrations: Database,
  Connectors: Database,
  Billing: CreditCard,
  Runs: Activity,
  FAQ: BookOpen,
}

export function categoryIcon(category: string): LucideIcon {
  return CATEGORY_ICONS[category] ?? BookOpen
}
