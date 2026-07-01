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
  "Command Center": Sparkles,
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

/**
 * One-line summaries shown on the "Browse by topic" cards. Keeps every card a
 * uniform height regardless of how many articles a category contains, instead
 * of dumping the full (and very uneven) list of links.
 */
const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  "Getting Started": "Set up your account and ship your first Run.",
  "Core Concepts": "How the platform, agents, and data model fit together.",
  Concepts: "How the platform, agents, and data model fit together.",
  "How-to Guides": "Task-focused walkthroughs for everyday workflows.",
  Guides: "Task-focused walkthroughs for everyday workflows.",
  "API Reference": "REST endpoints, authentication, and webhooks.",
  API: "REST endpoints, authentication, and webhooks.",
  Integrations: "Connect HubSpot, Salesforce, GitHub, and more.",
  Connectors: "Connect HubSpot, Salesforce, GitHub, and more.",
  Security: "Data handling, access controls, and compliance.",
  Billing: "Plans, pricing, and checkout.",
  FAQ: "Quick answers to the questions we hear most.",
}

export function categoryDescription(category: string): string {
  return CATEGORY_DESCRIPTIONS[category] ?? "Guides and reference for this area of Gravitre."
}

/**
 * Optional landing-page overrides for categories that have a dedicated hub
 * route (richer than linking to the first article). Anything not listed falls
 * back to the category's first doc.
 */
const CATEGORY_LANDING: Record<string, string> = {
  Integrations: "/docs/integrations",
  FAQ: "/docs/faq",
}

export function categoryLanding(category: string, fallbackHref: string): string {
  return CATEGORY_LANDING[category] ?? fallbackHref
}
