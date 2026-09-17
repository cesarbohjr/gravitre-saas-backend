"use client"

/**
 * Intelligence hub primary navigation — text links, not a pill strip.
 * Training is folded under Model Studio; `/training` remains routable.
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
  | "model-studio"
  | "reports"

export const INTELLIGENCE_HUB_TABS: Array<HubTabItem<IntelligenceHubTab>> = [
  { id: "overview", label: "Overview", href: APP_ROUTES.intelligence },
  { id: "learning", label: "Learning", href: APP_ROUTES.learning },
  { id: "predictions", label: "Predictions", href: APP_ROUTES.intelligencePredictive },
  { id: "performance", label: "Performance", href: APP_ROUTES.intelligencePerformance },
  { id: "models", label: "Models", href: APP_ROUTES.models },
  { id: "model-studio", label: "Model Studio", href: APP_ROUTES.intelligenceModelStudio },
  { id: "reports", label: "Reports", href: APP_ROUTES.intelligenceReports },
]

export function resolveIntelligenceHubTab(pathname: string): IntelligenceHubTab {
  if (pathname.startsWith("/intelligence/learning")) return "learning"
  if (pathname.startsWith("/intelligence/predictive")) return "predictions"
  if (pathname.startsWith("/intelligence/performance")) return "performance"
  if (pathname.startsWith("/intelligence/model-studio")) return "model-studio"
  if (pathname.startsWith("/models")) return "models"
  if (pathname.startsWith("/training")) return "model-studio"
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
      className={cn("mb-4 flex flex-wrap items-baseline gap-x-4 gap-y-1", className)}
    >
      {INTELLIGENCE_HUB_TABS.map((link) => {
        const isActive = current === link.id
        return (
          <Link
            key={link.id}
            href={link.href ?? APP_ROUTES.intelligence}
            aria-current={isActive ? "page" : undefined}
            className={cn(
              TYPE.meta,
              "underline-offset-4",
              isActive
                ? "text-[color:var(--g-text-primary)] underline"
                : "text-[color:var(--g-text-muted)] hover:text-[color:var(--g-text-primary)]",
            )}
          >
            {link.label}
          </Link>
        )
      })}
    </nav>
  )
}
