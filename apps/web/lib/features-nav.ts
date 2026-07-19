import type { LucideIcon } from "lucide-react"
import {
  BarChart3,
  Bot,
  Brain,
  LayoutGrid,
  Shield,
  Sparkles,
  Workflow,
  Blocks,
  Database,
  GitBranch,
} from "lucide-react"

export type FeaturesSectionId =
  | "overview"
  | "intelligence"
  | "how-it-works"
  | "gravitre-ai"
  | "agents"
  | "workflows"
  | "meson"
  | "integrations"
  | "governance"
  | "marketplace"
  | "insights"

export type FeaturesNavItem = {
  id: FeaturesSectionId
  href: string
  label: string
  description: string
  icon: LucideIcon
  group: "Platform" | "Intelligence" | "Trust"
}

export const FEATURES_NAV: FeaturesNavItem[] = [
  {
    id: "overview",
    href: "/features",
    label: "Overview",
    description: "Explore the full platform at a glance.",
    icon: LayoutGrid,
    group: "Platform",
  },
  {
    id: "how-it-works",
    href: "/features/how-it-works",
    label: "How it works",
    description: "Team → Gravitre AI → agents → tools, with approval at every write.",
    icon: GitBranch,
    group: "Platform",
  },
  {
    id: "gravitre-ai",
    href: "/features/gravitre-ai",
    label: "Gravitre AI",
    description: "Execute, chat, and search with live connector checks.",
    icon: Sparkles,
    group: "Platform",
  },
  {
    id: "agents",
    href: "/features/agents",
    label: "Agents",
    description: "Department agents with profiles, health, and verified outcomes.",
    icon: Bot,
    group: "Platform",
  },
  {
    id: "workflows",
    href: "/features/workflows",
    label: "Workflows",
    description: "Visual builder, simulation, failure predictions, and approvals.",
    icon: Workflow,
    group: "Platform",
  },
  {
    id: "meson",
    href: "/features/meson",
    label: "Meson",
    description: "One prompt → agents, datasets, and workflow drafts for review.",
    icon: Blocks,
    group: "Platform",
  },
  {
    id: "integrations",
    href: "/features/integrations",
    label: "Integrations",
    description: "50+ connectors with Configured → Executable readiness.",
    icon: Database,
    group: "Platform",
  },
  {
    id: "intelligence",
    href: "/features/intelligence",
    label: "GIBE",
    description: "Memory, ML catalog, routing traces, and org-scoped learning.",
    icon: Brain,
    group: "Intelligence",
  },
  {
    id: "insights",
    href: "/features/insights",
    label: "Metrics & use cases",
    description: "Honest reporting tiers and where teams start.",
    icon: BarChart3,
    group: "Intelligence",
  },
  {
    id: "governance",
    href: "/features/governance",
    label: "Governance",
    description: "Approval gates, audit trails, RBAC, and AI stack transparency.",
    icon: Shield,
    group: "Trust",
  },
]

export const FEATURES_NAV_GROUPS = ["Platform", "Intelligence", "Trust"] as const

export function getFeaturesNavItem(pathname: string): FeaturesNavItem | undefined {
  if (pathname === "/features") return FEATURES_NAV.find((item) => item.id === "overview")
  return FEATURES_NAV.find((item) => item.href === pathname)
}
