import { APP_ROUTES } from "@/lib/app-routes"
import type { WelcomeRoleId } from "@/lib/welcome-flow"

export type RoleQuickAction = {
  label: string
  href: string
}

export const ROLE_QUICK_ACTIONS: Record<WelcomeRoleId, RoleQuickAction[]> = {
  executive: [
    { label: "View org learning", href: APP_ROUTES.orgLearning },
    { label: "Revenue risk radar", href: APP_ROUTES.revenueRisk },
  ],
  sales: [
    { label: "View pipeline risks", href: APP_ROUTES.revenueRisk },
    { label: "Review recommendations", href: APP_ROUTES.intelligence },
  ],
  marketing: [
    { label: "Campaign insights", href: APP_ROUTES.intelligence },
    { label: "Agent profiles", href: APP_ROUTES.intelligenceAgents },
  ],
  ops: [
    { label: "Workflow bottlenecks", href: "/workflows/failure-predictions" },
    { label: "Process health", href: `${APP_ROUTES.orgLearning}#process-mining` },
  ],
  hr: [
    { label: "Agent training", href: APP_ROUTES.training },
    { label: "Memory explorer", href: APP_ROUTES.intelligenceMemory },
  ],
  finance: [
    { label: "Revenue risk radar", href: APP_ROUTES.revenueRisk },
    { label: "Executive reports", href: APP_ROUTES.intelligenceReports },
  ],
  support: [
    { label: "Pending approvals", href: APP_ROUTES.approvals },
    { label: "Chat", href: APP_ROUTES.gravitreAi },
  ],
  engineering: [
    { label: "Workflow runs", href: "/runs" },
    { label: "Failure alerts", href: "/workflows/failure-predictions" },
  ],
}
