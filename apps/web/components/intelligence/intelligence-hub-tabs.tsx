"use client"

/**
 * Intelligence hub primary navigation — text links, not a pill strip.
 *
 * One level only, grouped by the two jobs people come for:
 *   Understand
 *     Overview  → what is changing?
 *     Knowledge → what has Gravitre learned and remembered? (route /intelligence/learning; Memory lives here)
 *     Forecasts → what is likely to happen next? (route /intelligence/predictive)
 *     Impact    → what did agents deliver? (route /intelligence/performance)
 *     Reports   → shareable summaries.
 *   Build
 *     Data      → your datasets and public ones (Hugging Face, Kaggle).
 *     Models    → every model, yours and built-in; Model Studio is its "New model" flow.
 * Old routes (/training, /intelligence/memory, /intelligence/models) redirect.
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
  | "data"

export type IntelligenceHubGroup = "understand" | "build"

export const INTELLIGENCE_HUB_GROUPS: Array<{ id: IntelligenceHubGroup; label: string }> = [
  { id: "understand", label: "Understand" },
  { id: "build", label: "Build" },
]

export const INTELLIGENCE_HUB_TABS: Array<
  HubTabItem<IntelligenceHubTab> & { description: string; group: IntelligenceHubGroup }
> = [
  {
    id: "overview",
    label: "Overview",
    href: APP_ROUTES.intelligence,
    description: "What is changing across the business",
    group: "understand",
  },
  {
    id: "learning",
    label: "Knowledge",
    href: APP_ROUTES.learning,
    description: "What Gravitre has learned: confirmed facts, relationships, and memory",
    group: "understand",
  },
  {
    id: "predictions",
    label: "Forecasts",
    href: APP_ROUTES.intelligencePredictive,
    description: "Risks and opportunities Gravitre expects next",
    group: "understand",
  },
  {
    id: "performance",
    label: "Impact",
    href: APP_ROUTES.intelligencePerformance,
    description: "What your agents delivered: outcomes, time saved, and cost",
    group: "understand",
  },
  {
    id: "reports",
    label: "Reports",
    href: APP_ROUTES.intelligenceReports,
    description: "Shareable business summaries",
    group: "understand",
  },
  {
    id: "data",
    label: "Data",
    href: APP_ROUTES.intelligenceData,
    description: "Your datasets and public ones from Hugging Face and Kaggle, and what each one feeds",
    group: "build",
  },
  {
    id: "models",
    label: "Models",
    href: APP_ROUTES.models,
    description: "Every model behind forecasts and agents, yours and built-in; start a new one here",
    group: "build",
  },
]

export function resolveIntelligenceHubTab(pathname: string): IntelligenceHubTab {
  if (pathname.startsWith("/intelligence/learning")) return "learning"
  if (pathname.startsWith("/intelligence/memory")) return "learning"
  if (pathname.startsWith("/intelligence/data")) return "data"
  if (pathname.startsWith("/intelligence/predictive")) return "predictions"
  if (pathname.startsWith("/intelligence/performance")) return "performance"
  if (pathname.startsWith("/intelligence/model-studio")) return "models"
  if (pathname.startsWith("/models")) return "models"
  if (pathname.startsWith("/intelligence/models")) return "models"
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
      {INTELLIGENCE_HUB_GROUPS.map((group, groupIndex) => (
        <div
          key={group.id}
          role="group"
          aria-labelledby={`intelligence-hub-group-${group.id}`}
          className={cn(
            "flex shrink-0 flex-col",
            groupIndex > 0 && "border-l border-[color:var(--g-border-subtle)] pl-5",
          )}
        >
          <span
            id={`intelligence-hub-group-${group.id}`}
            className="pb-0.5 font-mono text-[10px] uppercase tracking-[0.08em] text-[color:var(--g-text-muted)]"
          >
            {group.label}
          </span>
          <div className="flex items-end gap-x-5">
            {INTELLIGENCE_HUB_TABS.filter((link) => link.group === group.id).map((link) => {
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
          </div>
        </div>
      ))}
    </nav>
  )
}
