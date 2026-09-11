"use client"

/**
 * Intelligence redesign Phase 1 (2026-09-11) — the new primary navigation for
 * the Intelligence family: Overview, Learning, Predictions, Performance,
 * Models, Model Studio, Training, Reports. All eight are first-class and
 * always visible — no collapsed "Advanced" drawer, per the redesign brief.
 *
 * This mirrors the existing `AgentsHubTabs` pattern (same `HubTabs` primitive)
 * rather than inventing a new nav vocabulary. Every href below already
 * resolves to a real, working page; no route was renamed to build this —
 * `/intelligence/predictive` keeps its URL and is simply labeled "Predictions"
 * here, so no bookmark or deep link breaks.
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
  | "training"
  | "reports"

const TABS: Array<HubTabItem<IntelligenceHubTab>> = [
  { id: "overview", label: "Overview", href: APP_ROUTES.intelligence },
  { id: "learning", label: "Learning", href: APP_ROUTES.learning },
  { id: "predictions", label: "Predictions", href: APP_ROUTES.intelligencePredictive },
  { id: "performance", label: "Performance", href: APP_ROUTES.intelligencePerformance },
  { id: "models", label: "Models", href: APP_ROUTES.models },
  { id: "model-studio", label: "Model Studio", href: APP_ROUTES.intelligenceModelStudio },
  { id: "training", label: "Training", href: APP_ROUTES.training },
  { id: "reports", label: "Reports", href: APP_ROUTES.intelligenceReports },
]

export function resolveIntelligenceHubTab(pathname: string): IntelligenceHubTab {
  if (pathname.startsWith("/intelligence/learning") || pathname.startsWith("/admin/intelligence")) {
    return "learning"
  }
  if (pathname.startsWith("/intelligence/predictive")) return "predictions"
  if (pathname.startsWith("/intelligence/performance")) return "performance"
  if (pathname.startsWith("/intelligence/model-studio")) return "model-studio"
  if (pathname.startsWith("/models")) return "models"
  if (pathname.startsWith("/training")) return "training"
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
