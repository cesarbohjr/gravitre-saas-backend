import ActivityPage from "@/app/(app)/activity/page"
import AgentsPage from "@/app/(app)/agents/page"
import AiWorkspaceCapturePage from "./_components/ai-workspace-capture-page"
import ApprovalsPage from "@/app/(app)/approvals/page"
import AssignmentsPage from "@/app/(app)/assignments/page"
import ConnectorsPage from "@/app/(app)/connectors/page"
import HomePage from "@/app/(app)/home/page"
import IntelligencePage from "@/app/(app)/intelligence/page"
import IntelligencePerformancePage from "@/app/(app)/intelligence/performance/page"
import IntelligencePredictivePage from "@/app/(app)/intelligence/predictive/page"
import IntelligenceReportsPage from "@/app/(app)/intelligence/reports/page"
import IntelligenceLearningPage from "@/app/(app)/intelligence/learning/page"
import MarketplaceAssetsPage from "@/app/(app)/marketplace/assets/page"
import MarketplaceInstalledPage from "@/app/(app)/marketplace/installed/page"
import SourcesPage from "@/app/(app)/sources/page"
import MetricsPage from "@/app/(app)/metrics/page"
import WorkflowsPage from "@/app/(app)/workflows/page"
import SchedulesPage from "@/app/(app)/schedules/page"
import ModelsPage from "@/app/(app)/models/page"
import TrainingPage from "@/app/(app)/training/page"
import IntelligenceDataPage from "@/app/(app)/intelligence/data/page"
import ModelStudioPage from "@/app/(app)/intelligence/model-studio/page"
import GoalsPage from "@/app/(app)/goals/page"
import PlaysPage from "@/app/(app)/plays/page"
import SettingsPage from "@/app/(app)/settings/page"
import SettingsApprovalsPage from "@/app/(app)/settings/approvals/page"
import AuditPage from "@/app/(app)/audit/page"
import AiWorkspaceProofPage from "./_components/ai-workspace-proof-page"
import AgentChatProofPage from "./_components/agent-chat-proof-page"
import NotificationsPage from "@/app/(app)/notifications/page"
import LiteTasksPage from "@/app/(app)/lite/tasks/page"
import LiteAssignPage from "@/app/(app)/lite/assign/page"
import LiteResultsPage from "@/app/(app)/lite/results/page"
import LiteDeliverablesPage from "@/app/(app)/lite/deliverables/page"
import WelcomePage from "@/app/welcome/page"

import { GravitreAIWorkspaceHost } from "@/components/gravitre/ai-workspace-host"
import { ShotAuthProvider } from "./shot-auth"

/**
 * Real product surfaces available for capture.
 *
 * Deliberately static routes rather than one `[view]` dynamic segment: under
 * this layout the dynamic param came through empty, so every request fell into
 * the `notFound()` branch and looked like a routing/auth failure. Static
 * children are unambiguous and cheap here — there are only a few surfaces.
 */
export const SHOT_SURFACES = {
  activity: ActivityPage,
  agents: AgentsPage,
  ai: AiWorkspaceCapturePage,
  approvals: ApprovalsPage,
  assignments: AssignmentsPage,
  connectors: ConnectorsPage,
  home: HomePage,
  "intelligence-field": IntelligencePage,
  "intelligence-performance": IntelligencePerformancePage,
  "intelligence-predictive": IntelligencePredictivePage,
  "intelligence-reports": IntelligenceReportsPage,
  "intelligence-learning": IntelligenceLearningPage,
  // Memory is a section of Knowledge now; the old surface name still captures it.
  "intelligence-memory": IntelligenceLearningPage,
  marketplace: MarketplaceAssetsPage,
  "marketplace-installed": MarketplaceInstalledPage,
  workflows: WorkflowsPage,
  schedules: SchedulesPage,
  models: ModelsPage,
  goals: GoalsPage,
  plays: PlaysPage,
  settings: SettingsPage,
  "settings-approvals": SettingsApprovalsPage,
  audit: AuditPage,
  training: TrainingPage,
  "intelligence-data": IntelligenceDataPage,
  "model-studio": ModelStudioPage,
  sources: SourcesPage,
  metrics: MetricsPage,
  proof: AiWorkspaceProofPage,
  "agent-chat": AgentChatProofPage,
  notifications: NotificationsPage,
  "lite-tasks": LiteTasksPage,
  "lite-assign": LiteAssignPage,
  "lite-results": LiteResultsPage,
  "lite-deliverables": LiteDeliverablesPage,
  welcome: WelcomePage,
} as const

export function ShotSurface({ name }: { name: keyof typeof SHOT_SURFACES }) {
  const Surface = SHOT_SURFACES[name]
  return (
    <ShotAuthProvider>
      <Surface />
      {name !== "ai" && name !== "welcome" ? <GravitreAIWorkspaceHost fixtureBoundary /> : null}
    </ShotAuthProvider>
  )
}
