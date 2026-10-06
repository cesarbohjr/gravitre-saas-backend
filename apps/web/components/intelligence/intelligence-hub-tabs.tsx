"use client"

/**
 * Intelligence hub primary navigation — text links, not a pill strip.
 *
 * One level only, one noun per question a user asks:
 *   Overview  → what is changing?
 *   Knowledge → what has Gravitre learned? (route stays /intelligence/learning)
 *   Forecasts → what is likely to happen next? (route stays /intelligence/predictive)
 *   Impact    → what did agents deliver? (route stays /intelligence/performance)
 *   Models    → which models power this, and how do I train one?
 *   Reports   → shareable summaries.
 * Model Studio and `/training` live under Models; their routes stay valid.
 */
import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { TYPE } from "@/lib/design-system"
import { APP_ROUTES } from "@/lib/app-routes"
import type { HubTabItem } from "@/components/gravitre/hub-tabs"

export type IntelligenceHubTab =
  | "overview"
  | "learning"
  | "predictions"
  | "performance"
  | "models"
  | "reports"

export const INTELLIGENCE_HUB_TABS: Array<HubTabItem<IntelligenceHubTab> & { description: string }> = [
  {
    id: "overview",
    label: "Overview",
    href: APP_ROUTES.intelligence,
    description: "What is changing across the business",
  },
  {
    id: "learning",
    label: "Knowledge",
    href: APP_ROUTES.learning,
    description: "What Gravitre has learned: confirmed facts, relationships, and memory",
  },
  {
    id: "predictions",
    label: "Forecasts",
    href: APP_ROUTES.intelligencePredictive,
    description: "Risks and opportunities Gravitre expects next",
  },
  {
    id: "performance",
    label: "Impact",
    href: APP_ROUTES.intelligencePerformance,
    description: "What your agents delivered: outcomes, time saved, and cost",
  },
  {
    id: "models",
    label: "Models",
    href: APP_ROUTES.models,
    description: "The models behind forecasts and agents; create and train them in Model Studio",
  },
  {
    id: "reports",
    label: "Reports",
    href: APP_ROUTES.intelligenceReports,
    description: "Shareable business summaries",
  },
]

export function resolveIntelligenceHubTab(pathname: string): IntelligenceHubTab {
  if (pathname.startsWith("/intelligence/learning")) return "learning"
  if (pathname.startsWith("/intelligence/predictive")) return "predictions"
  if (pathname.startsWith("/intelligence/performance")) return "performance"
  if (pathname.startsWith("/intelligence/model-studio")) return "models"
  if (pathname.startsWith("/models")) return "models"
  if (pathname.startsWith("/training")) return "models"
  if (pathname.startsWith("/intelligence/reports")) return "reports"
  return "overview"
}

export function IntelligenceHubTabs({
  active,
  className,
}: {
  active?: IntelligenceHubTab
  className?: string
}) {
  const pathname = usePathname()
  const current = active ?? resolveIntelligenceHubTab(pathname ?? "")

  return (
    <nav
      aria-label="Intelligence hub"
      className={cn(
        "-mb-px flex items-end gap-x-5 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
        className,
      )}
    >
      {INTELLIGENCE_HUB_TABS.map((link) => {
        const isActive = current === link.id
        return (
          <Link
            key={link.id}
            href={link.href ?? APP_ROUTES.intelligence}
            aria-current={isActive ? "page" : undefined}
            title={link.description}
            className={cn(
              TYPE.meta,
              "relative inline-flex min-h-11 shrink-0 items-end whitespace-nowrap pb-2.5 pt-1 text-[13px] sm:min-h-0 font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              "after:absolute after:inset-x-0 after:bottom-0 after:h-[2px] after:rounded-full",
              isActive
                ? "text-[color:var(--g-text-primary)] after:bg-[color:var(--g-intelligence)]"
                : "text-[color:var(--g-text-muted)] after:bg-transparent hover:text-[color:var(--g-text-primary)]",
            )}
          >
            {link.label}
          </Link>
        )
      })}
    </nav>
  )
}
