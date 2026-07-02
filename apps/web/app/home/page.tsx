"use client"

import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { PageHeader, StatCard, StatsGrid } from "@/components/gravitre/page-header"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import {
  architectureAdminApi,
  intelligenceApi,
  approvalsApi,
} from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { fetcher } from "@/lib/fetcher"
import {
  roleFromOnboardingStepData,
  WELCOME_ROLES,
  type WelcomeRoleId,
} from "@/lib/welcome-flow"
import { AiWorkSurfacesCallout } from "@/components/gravitre/ai-work-surfaces-callout"
import { GridPattern } from "@/components/gravitre/premium-effects"
import {
  ArrowRight,
  Brain,
  ChartLineUp,
  ClipboardText,
  RocketLaunch,
  Sparkle,
  WarningCircle,
} from "@phosphor-icons/react"
import type { OnboardingProgress } from "@/types/api"

const ROLE_QUICK_ACTIONS: Record<
  WelcomeRoleId,
  Array<{ label: string; href: string; description: string }>
> = {
  executive: [
    { label: "Executive reports", href: APP_ROUTES.intelligenceReports, description: "ROI and department scorecards" },
    { label: "Intelligence Center", href: APP_ROUTES.intelligence, description: "Trust, outcomes, and simulations" },
    { label: "Org Learning", href: APP_ROUTES.orgLearning, description: "What Gravitre is learning" },
  ],
  marketing: [
    { label: "Marketing pack", href: "/marketplace/assets/marketing-operations-pack", description: "Agents + workflows for campaigns" },
    { label: "Connect HubSpot", href: "/connectors?type=hubspot", description: "CRM + attribution context" },
    { label: "Start AI chat", href: APP_ROUTES.gravitreAi, description: "Draft campaign briefs" },
  ],
  sales: [
    { label: "RevOps pack", href: "/marketplace/assets/revenue-operations-pack", description: "Pipeline agents" },
    { label: "Connect CRM", href: "/connectors?type=salesforce", description: "Salesforce or HubSpot" },
    { label: "Command Center", href: APP_ROUTES.commandCenter, description: "Delegate pipeline review" },
  ],
  ops: [
    { label: "Workflows", href: APP_ROUTES.workflows, description: "Build and monitor automations" },
    { label: "Failure alerts", href: "/workflows/failure-predictions", description: "Predicted run failures" },
    { label: "Runs", href: "/runs", description: "Execution history" },
  ],
  hr: [
    { label: "HR pack", href: "/marketplace/assets/hr-operations-pack", description: "Policy + onboarding flows" },
    { label: "Connect Slack", href: "/connectors?type=slack", description: "Employee comms" },
    { label: "Agent Training", href: APP_ROUTES.training, description: "Fine-tune policy responses" },
  ],
  finance: [
    { label: "Connect QuickBooks", href: "/connectors?type=quickbooks", description: "Invoices and AR" },
    { label: "Model Registry", href: APP_ROUTES.models, description: "Revenue + churn models" },
    { label: "Approvals", href: APP_ROUTES.approvals, description: "Review finance actions" },
  ],
  support: [
    { label: "CS pack", href: "/marketplace/assets/customer-success-pack", description: "Ticket triage agents" },
    { label: "Connect Zendesk", href: "/connectors?type=zendesk", description: "Support context" },
    { label: "Multi-Agent Run", href: APP_ROUTES.multiAgentRun, description: "Parallel ticket analysis" },
  ],
  engineering: [
    { label: "Connect GitHub", href: "/connectors?type=github", description: "PRs and incidents" },
    { label: "Runs", href: "/runs", description: "Failed workflow steps" },
    { label: "Agents", href: APP_ROUTES.agents, description: "DevOps agent profiles" },
  ],
}

export default function HomePage() {
  const { user } = useAuth()
  const { data: onboarding } = useSWR<OnboardingProgress>(
    user ? "/api/onboarding" : null,
    fetcher,
    { revalidateOnFocus: false },
  )
  const { data: learning } = useSWR(
    user ? "home/learning-progress" : null,
    () => intelligenceApi.learningProgress(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: trust } = useSWR(
    user ? "home/trust" : null,
    () => intelligenceApi.trustSummary({ periodDays: 7 }),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: businessImpact } = useSWR(
    user ? "home/business-impact" : null,
    () => intelligenceApi.businessImpact(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: aiOs } = useSWR(
    user ? "home/ai-os" : null,
    () => architectureAdminApi.aiOsStatus(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: predictive } = useSWR(
    user ? "home/predictive" : null,
    () => architectureAdminApi.predictiveOps(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: approvalsData } = useSWR(
    user ? "home/approvals" : null,
    () => approvalsApi.list(),
    { revalidateOnFocus: false },
  )

  const roleId =
    roleFromOnboardingStepData(onboarding?.step_data) ??
    (WELCOME_ROLES[0]?.id as WelcomeRoleId)
  const roleMeta = WELCOME_ROLES.find((entry) => entry.id === roleId) ?? WELCOME_ROLES[0]
  const quickActions = ROLE_QUICK_ACTIONS[roleId] ?? ROLE_QUICK_ACTIONS.ops

  const pendingApprovals = approvalsData?.approvals?.length ?? 0

  const revenueRisks = businessImpact?.revenueRiskItems ?? []
  const avgConfidence =
    typeof trust?.avg_confidence === "number"
      ? Math.round(trust.avg_confidence * 100)
      : typeof trust?.avgConfidence === "number"
        ? Math.round(trust.avgConfidence * 100)
        : null

  const mlActive = typeof aiOs?.ml_models_active === "number" ? aiOs.ml_models_active : null
  const memoriesCount = typeof aiOs?.memories_count === "number" ? aiOs.memories_count : null

  return (
    <AppShell title="Home">
      <div className="relative min-h-full">
        <GridPattern className="opacity-[0.25]" />
        <div className="relative z-10 mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
          <PageHeader
            title={`Welcome back${roleMeta ? `, ${roleMeta.label}` : ""}`}
            description="Your role-aware home for delegating work, monitoring intelligence, and clearing approvals."
            icon={RocketLaunch}
            iconColor="from-emerald-500/20 to-blue-500/20"
            className="border-0 p-0"
            actions={
              <Button asChild size="sm">
                <Link href={APP_ROUTES.gravitreAi}>Open Gravitre AI</Link>
              </Button>
            }
          />

          <AiWorkSurfacesCallout current="command-center" compact />

          <section className="space-y-3">
            <h2 className="text-sm font-medium text-muted-foreground">Quick actions for your role</h2>
            <div className="grid gap-3 md:grid-cols-3">
              {quickActions.map((action) => (
                <Link
                  key={action.href}
                  href={action.href}
                  className="rounded-xl border border-border/70 bg-card/50 p-4 transition-colors hover:bg-muted/30"
                >
                  <p className="text-sm font-medium text-foreground">{action.label}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{action.description}</p>
                </Link>
              ))}
            </div>
          </section>

          <StatsGrid columns={4}>
            <StatCard
              label="Pending approvals"
              value={pendingApprovals}
              variant={pendingApprovals > 0 ? "warning" : "success"}
            />
            <StatCard
              label="Avg confidence (7d)"
              value={avgConfidence != null ? `${avgConfidence}%` : "—"}
              variant="info"
            />
            <StatCard
              label="Query rows logged"
              value={learning?.queryRows ?? "—"}
              variant="default"
            />
            <StatCard
              label="Workflow rows"
              value={learning?.workflowRows ?? "—"}
              variant="default"
            />
          </StatsGrid>

          <div className="grid gap-4 lg:grid-cols-2">
            <DashboardPanel
              title="Intelligence health"
              icon={Sparkle}
              href={APP_ROUTES.intelligence}
              linkLabel="View Intelligence Center"
            >
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>ML models active: {mlActive ?? "—"}</li>
                <li>Memories accumulated: {memoriesCount ?? "—"}</li>
                <li>
                  Learning progress: {learning?.queryRows ?? 0}/{learning?.queryRowsNeeded ?? "—"} queries,{" "}
                  {learning?.workflowRows ?? 0}/{learning?.workflowRowsNeeded ?? "—"} workflow runs
                </li>
              </ul>
            </DashboardPanel>

            <DashboardPanel
              title="Revenue risk radar"
              icon={WarningCircle}
              href={APP_ROUTES.orgLearning}
              linkLabel="View in Org Learning"
            >
              {revenueRisks.length === 0 ? (
                <p className="text-sm text-muted-foreground">No revenue risk signals detected this week.</p>
              ) : (
                <ul className="space-y-2">
                  {revenueRisks.slice(0, 3).map((risk) => (
                    <li key={risk.id} className="rounded-lg border border-border/60 px-3 py-2 text-sm">
                      <span className="font-medium text-foreground">{risk.title}</span>
                      <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{risk.summary}</p>
                    </li>
                  ))}
                </ul>
              )}
            </DashboardPanel>

            <DashboardPanel
              title="Predictive operations"
              icon={ChartLineUp}
              href={APP_ROUTES.intelligence}
              linkLabel="Explore forecasts"
            >
              <p className="text-sm text-muted-foreground">
                {typeof predictive?.summary === "string"
                  ? predictive.summary
                  : "Workflow success trends and anomaly signals appear here once enough run history exists."}
              </p>
            </DashboardPanel>

            <DashboardPanel
              title="What Gravitre is learning"
              icon={Brain}
              href={APP_ROUTES.orgLearning}
              linkLabel="Open Org Learning"
            >
              <p className="text-sm text-muted-foreground">
                {learning?.hasAnySnapshot
                  ? "Gravitre is capturing query patterns, workflow outcomes, and memory promotion candidates."
                  : "Connect tools and run your first workflow — Gravitre starts learning as soon as data flows in."}
              </p>
              {pendingApprovals > 0 ? (
                <Link
                  href={APP_ROUTES.approvals}
                  className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-amber-600 dark:text-amber-400"
                >
                  <ClipboardText className="h-4 w-4" />
                  {pendingApprovals} approval{pendingApprovals === 1 ? "" : "s"} waiting
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              ) : null}
            </DashboardPanel>
          </div>

          <p className="text-xs text-muted-foreground">
            Resume setup from{" "}
            <Link href={APP_ROUTES.welcome} className="underline underline-offset-2 hover:text-foreground">
              Getting Started
            </Link>
            .
          </p>
        </div>
      </div>
    </AppShell>
  )
}

function DashboardPanel({
  title,
  icon: Icon,
  href,
  linkLabel,
  children,
}: {
  title: string
  icon: React.ComponentType<{ className?: string; weight?: "duotone" | "regular" }>
  href: string
  linkLabel: string
  children: React.ReactNode
}) {
  return (
    <section className="rounded-2xl border border-border/70 bg-card/50 p-5">
      <div className="mb-3 flex items-center gap-2">
        <Icon className="h-5 w-5 text-primary" weight="duotone" />
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      </div>
      {children}
      <Link href={href} className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
        {linkLabel}
        <ArrowRight className="h-3 w-3" />
      </Link>
    </section>
  )
}
