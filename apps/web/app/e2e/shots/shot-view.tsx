import ActivityPage from "@/app/activity/page"
import AgentsPage from "@/app/agents/page"
import AiWorkspaceCapturePage from "./_components/ai-workspace-capture-page"
import ApprovalsPage from "@/app/approvals/page"
import AssignmentsPage from "@/app/assignments/page"
import ConnectorsPage from "@/app/connectors/page"
import HomePage from "@/app/home/page"
import IntelligencePage from "@/app/intelligence/page"
import IntelligencePerformancePage from "@/app/intelligence/performance/page"
import IntelligencePredictivePage from "@/app/intelligence/predictive/page"
import IntelligenceReportsPage from "@/app/intelligence/reports/page"
import IntelligenceLearningPage from "@/app/intelligence/learning/page"
import IntelligenceMemoryPage from "@/app/intelligence/memory/page"
import MarketplaceAssetsPage from "@/app/marketplace/assets/page"
import MarketplaceInstalledPage from "@/app/marketplace/installed/page"
import SourcesPage from "@/app/sources/page"
import MetricsPage from "@/app/metrics/page"
import WorkflowsPage from "@/app/workflows/page"
import SchedulesPage from "@/app/schedules/page"
import ModelsPage from "@/app/models/page"
import TrainingPage from "@/app/training/page"
import AiWorkspaceProofPage from "./_components/ai-workspace-proof-page"
import AgentChatProofPage from "./_components/agent-chat-proof-page"

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
  "intelligence-memory": IntelligenceMemoryPage,
  marketplace: MarketplaceAssetsPage,
  "marketplace-installed": MarketplaceInstalledPage,
  workflows: WorkflowsPage,
  schedules: SchedulesPage,
  models: ModelsPage,
  training: TrainingPage,
  sources: SourcesPage,
  metrics: MetricsPage,
  proof: AiWorkspaceProofPage,
  "agent-chat": AgentChatProofPage,
} as const

export function ShotSurface({ name }: { name: keyof typeof SHOT_SURFACES }) {
  const Surface = SHOT_SURFACES[name]
  return (
    <ShotAuthProvider>
      <Surface />
      {name !== "ai" ? <GravitreAIWorkspaceHost fixtureBoundary /> : null}
    </ShotAuthProvider>
  )
}
