"use client"

/**
 * Intelligence hub primary navigation — I1 (7 tabs).
 * Training is folded under Model Studio; `/training` remains routable.
 */
import { usePathname } from "next/navigation"
import { HubTabs, type HubTabItem } from "@/components/gravitre/hub-tabs"
import { APP_ROUTES } from "@/lib/app-routes"

export type IntelligenceHubTab =
  | "overview"
  | "learning"
  | "predictions"
  | "performance"
  | "models"
  | "model-studio"
  | "reports"

const TABS: Array<HubTabItem<IntelligenceHubTab>> = [
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
    <HubTabs
      tabs={TABS}
      active={current}
      ariaLabel="Intelligence hub"
      className={className ?? "mb-4 flex-wrap"}
    />
  )
}
