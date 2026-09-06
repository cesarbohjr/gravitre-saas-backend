"use client"

/**
 * Authenticated home command surface (UI 2.0 Pilot B).
 * PageHeader + TYPE · real status chips only · elevation surfaces.
 * No fabricated weekly confidence series, fake predictive bars, or invented "Live" claims.
 */

import type React from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import {
  ArrowRight,
  Brain,
  ChartLineUp,
  CheckCircle,
  ClipboardText,
  Clock,
  Cpu,
  Database,
  Robot,
  Sparkle,
  WarningCircle,
} from "@phosphor-icons/react"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { Button } from "@/components/ui/button"
import {
  AnimatedCounter,
} from "@/components/gravitre/premium-effects"
import { PageHeader, StatCard, StatsGrid } from "@/components/gravitre/page-header"
import { APP_ROUTES } from "@/lib/app-routes"
import { relativeTime } from "@/lib/agent-job-result"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { cardVariants, useMotionPrefs } from "@/lib/animations"
import { RADIUS, TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { PulseDot, StatusChip } from "@/components/gravitre/visual"
import type { WelcomeRoleId } from "@/lib/welcome-flow"
import { ROLE_QUICK_ACTIONS } from "@/lib/role-quick-actions"

type HomeDashboardProps = {
  roleId: WelcomeRoleId
  roleLabel: string
  pendingApprovals: number
  pendingApprovalItems?: Array<{ id: string; title?: string }>
  avgConfidence: number | null
  queryRows: number
  queryRowsNeeded: number
  workflowRows: number
  workflowRowsNeeded: number
  hasLearningSnapshot: boolean
  mlActive: number | null
  memoriesCount: number | null
  aiSystemsOnline?: number | null
  lastLearningCycle?: string | null
  revenueRisks: Array<{ id: string; title: string; summary: string }>
  predictiveSummary: string | null
  readyModelCount?: number | null
  learningVelocity?: string | null
  showGettingStarted: boolean
  showRoleQuickActions?: boolean
}

function pct(current: number, needed: number) {
  if (!needed || needed <= 0) return current > 0 ? 100 : 0
  return Math.max(0, Math.min(100, Math.round((current / needed) * 100)))
}

export function HomeDashboard({
  roleId,
  roleLabel,
  pendingApprovals,
  pendingApprovalItems = [],
  avgConfidence,
  queryRows,
  queryRowsNeeded,
  workflowRows,
  workflowRowsNeeded,
  hasLearningSnapshot,
  mlActive,
  memoriesCount,
  aiSystemsOnline,
  lastLearningCycle,
  revenueRisks,
  predictiveSummary,
  readyModelCount,
  learningVelocity,
  showGettingStarted,
  showRoleQuickActions = false,
}: HomeDashboardProps) {
  const { reduced, container, item } = useMotionPrefs()
  const quickActions = ROLE_QUICK_ACTIONS[roleId] ?? ROLE_QUICK_ACTIONS.ops
  const showQuickActions =
    (showRoleQuickActions || showGettingStarted) && quickActions.length > 0

  const queryPct = pct(queryRows, queryRowsNeeded || 50)
  const workflowPct = pct(workflowRows, workflowRowsNeeded || 30)
  const onlineSystems = aiSystemsOnline ?? mlActive ?? null
  const lastCycleLabel = lastLearningCycle ? relativeTime(lastLearningCycle) : null

  const learningBars = [
    { name: "Queries", current: queryRows, target: queryRowsNeeded || 50, fill: "var(--info)" },
    { name: "Workflows", current: workflowRows, target: workflowRowsNeeded || 30, fill: "var(--success)" },
  ]

  const systemStats = [
    {
      label: "AI systems online",
      value: onlineSystems != null ? String(onlineSystems) : "—",
      status: onlineSystems != null && onlineSystems > 0 ? ("active" as const) : ("idle" as const),
      known: onlineSystems != null,
      icon: Cpu,
    },
    {
      label: "ML models active",
      value: mlActive != null ? String(mlActive) : "—",
      status: mlActive != null && mlActive > 0 ? ("processing" as const) : ("idle" as const),
      known: mlActive != null,
      icon: Robot,
    },
    {
      label: "Memories",
      value: memoriesCount != null ? memoriesCount.toLocaleString() : "—",
      status: memoriesCount != null && memoriesCount > 0 ? ("active" as const) : ("idle" as const),
      known: memoriesCount != null,
      icon: Database,
    },
  ]

  return (
    <div className="relative w-full overflow-x-hidden">
      <motion.div
        variants={reduced ? undefined : container}
        initial="initial"
        animate="animate"
        className="relative z-10 mx-auto max-w-6xl space-y-5 pb-8 sm:pb-10"
      >
        <motion.div variants={item}>
          <PageHeader
            eyebrow="Home"
            title={`Welcome back, ${roleLabel}`}
            description="Monitor learning, clear approvals, and open Gravitre AI — status below reflects live API data only."
            icon={NucleoIntelligence}
            actions={
              <>
                <Button asChild size="sm">
                  <Link href={APP_ROUTES.gravitreAi}>
                    <Sparkle className="h-4 w-4" weight="fill" />
                    Open Gravitre AI
                  </Link>
                </Button>
                {pendingApprovals > 0 ? (
                  <Button asChild size="sm" variant="outline">
                    <Link href={APP_ROUTES.approvals}>
                      <ClipboardText className="h-4 w-4" />
                      {pendingApprovals} approval{pendingApprovals === 1 ? "" : "s"}
                    </Link>
                  </Button>
                ) : null}
                {showQuickActions
                  ? quickActions.map((action) => (
                      <Button
                        key={action.href}
                        asChild
                        size="sm"
                        variant="ghost"
                        className="text-muted-foreground"
                      >
                        <Link href={action.href}>
                          {action.label}
                          <ArrowRight className="h-3.5 w-3.5" />
                        </Link>
                      </Button>
                    ))
                  : null}
              </>
            }
          >
            {/* Phase 4–aligned chips: only when backend-backed values exist */}
            <div className="flex flex-wrap items-center gap-2">
              {pendingApprovals > 0 ? (
                <StatusChip tone="pending" href={APP_ROUTES.approvals} pulse>
                  Pending approval · {pendingApprovals}
                </StatusChip>
              ) : (
                <StatusChip tone="approved" href={APP_ROUTES.approvals}>
                  Approvals clear
                </StatusChip>
              )}
              {avgConfidence != null ? (
                <StatusChip tone="estimate" href={APP_ROUTES.intelligence}>
                  Avg confidence · 7d · {avgConfidence}%
                </StatusChip>
              ) : (
                <StatusChip tone="idle">Confidence · not yet available</StatusChip>
              )}
              {hasLearningSnapshot ? (
                <StatusChip tone="idle" href={APP_ROUTES.learning}>
                  Learning snapshot present
                </StatusChip>
              ) : (
                <StatusChip tone="idle">Learning · warming up</StatusChip>
              )}
            </div>
          </PageHeader>
        </motion.div>

        <motion.section
          variants={item}
          className={cn(
            "border border-border bg-card p-4 shadow-sm sm:p-5",
            RADIUS.panel,
          )}
        >
          <div className="flex items-center justify-between gap-3">
            <p className={TYPE.eyebrow}>System status</p>
            <Link
              href={APP_ROUTES.intelligence}
              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
            >
              Details
              <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            {systemStats.map((stat) => (
              <div
                key={stat.label}
                className={cn(
                  "flex items-center justify-between border border-border bg-background px-3 py-2",
                  RADIUS.tile,
                )}
              >
                <span className="flex items-center gap-2 text-xs text-muted-foreground">
                  <stat.icon className="h-4 w-4 text-primary" weight="duotone" />
                  {stat.label}
                </span>
                <span className="flex items-center gap-2 text-sm font-semibold tabular-nums text-foreground">
                  {stat.value}
                  {stat.known ? (
                    <PulseDot
                      tone={stat.status === "processing" ? "intelligence" : "emerald"}
                      size="sm"
                      label={stat.status}
                    />
                  ) : null}
                </span>
              </div>
            ))}
          </div>
          <p className={cn(TYPE.meta, "mt-3 flex items-center gap-2")}>
            <Clock className="h-3.5 w-3.5" />
            Last learning cycle:{" "}
            <span className="text-foreground">{lastCycleLabel ?? "—"}</span>
          </p>
        </motion.section>

        <motion.div variants={item}>
          <StatsGrid columns={4}>
            <StatCard
              label="Pending approvals"
              value={<AnimatedCounter value={pendingApprovals} className="tabular-nums" />}
              variant={pendingApprovals > 0 ? "warning" : "success"}
            />
            <StatCard
              label="Avg confidence · 7d"
              value={avgConfidence != null ? `${avgConfidence}%` : "—"}
              variant={avgConfidence != null ? "info" : "default"}
            />
            <StatCard
              label="Query rows logged"
              value={<AnimatedCounter value={queryRows} className="tabular-nums" />}
              variant="info"
            />
            <StatCard
              label="Workflow rows"
              value={<AnimatedCounter value={workflowRows} className="tabular-nums" />}
              variant="success"
            />
          </StatsGrid>
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-muted-foreground lg:grid-cols-4">
            <Link href={APP_ROUTES.approvals} className="hover:text-foreground hover:underline">
              {pendingApprovals > 0 ? "Needs your decision →" : "All clear →"}
            </Link>
            <Link href={APP_ROUTES.intelligence} className="hover:text-foreground hover:underline">
              {avgConfidence != null ? "From trust summary →" : "Warming up →"}
            </Link>
            <Link href={APP_ROUTES.learning} className="hover:text-foreground hover:underline">
              {queryRows}/{queryRowsNeeded || 50} to learn →
            </Link>
            <Link href={APP_ROUTES.learning} className="hover:text-foreground hover:underline">
              {workflowRows}/{workflowRowsNeeded || 30} observed →
            </Link>
          </div>
          {/* Progress for learning targets (real row counts) */}
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <ProgressFooter percent={queryPct} caption="Query progress toward learning target" accent="info" />
            <ProgressFooter percent={workflowPct} caption="Workflow progress toward observed target" accent="success" />
          </div>
        </motion.div>

        <div className="grid gap-4 lg:grid-cols-5">
          {pendingApprovals > 0 ? (
            <motion.section
              variants={item}
              className={cn(
                "relative flex flex-col border border-warning/30 bg-warning/5 p-5 shadow-sm lg:col-span-2",
                RADIUS.panel,
              )}
            >
              <PanelHeader
                icon={ClipboardText}
                title="Awaiting your approval"
                href={APP_ROUTES.approvals}
                linkLabel="Review all"
              />
              <p className={cn(TYPE.bodyMuted, "mt-2")}>
                {pendingApprovals} item{pendingApprovals === 1 ? "" : "s"} need your decision before
                agents can proceed.
              </p>
              <ul className="mt-3 space-y-2">
                {pendingApprovalItems.slice(0, 3).map((approval) => (
                  <li key={approval.id}>
                    <Link
                      href={APP_ROUTES.approvals}
                      className={cn(
                        "flex items-center justify-between border border-border bg-card px-3 py-2 text-sm text-foreground transition-colors hover:border-warning/40 hover:bg-warning/5",
                        RADIUS.tile,
                      )}
                    >
                      <span className="truncate">
                        {approval.title ?? `Approval ${approval.id.slice(0, 8)}`}
                      </span>
                      <ArrowRight className="h-4 w-4 shrink-0 text-warning" />
                    </Link>
                  </li>
                ))}
              </ul>
              <Button asChild size="sm" variant="outline" className="mt-4 w-full sm:mt-auto">
                <Link href={APP_ROUTES.approvals}>
                  Review {pendingApprovals} approval{pendingApprovals === 1 ? "" : "s"}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </motion.section>
          ) : (
            <motion.section
              variants={item}
              className={cn(
                "border border-success/25 bg-success/5 p-5 shadow-sm lg:col-span-2",
                RADIUS.panel,
              )}
            >
              <PanelHeader
                icon={CheckCircle}
                title="You're all caught up"
                href={APP_ROUTES.approvals}
                linkLabel="View queue"
              />
              <p className={cn(TYPE.bodyMuted, "mt-4")}>
                No approvals waiting. Agents proceed only within policy and existing gates.
              </p>
            </motion.section>
          )}

          <motion.section
            variants={item}
            className={cn(
              "border border-border bg-card p-5 shadow-sm lg:col-span-3",
              RADIUS.panel,
            )}
          >
            <PanelHeader
              icon={Sparkle}
              title="Confidence (trust summary)"
              href={APP_ROUTES.intelligence}
              linkLabel={SURFACE_COPY.insights.title}
            />
            {avgConfidence != null ? (
              <div className="mt-6 flex flex-col items-start gap-2">
                <p className={TYPE.metricValue}>{avgConfidence}%</p>
                <p className={TYPE.metricLabel}>Average confidence · last 7 days</p>
                <p className={TYPE.bodyMuted}>
                  Sourced from the trust summary API — not a fabricated weekly sparkline.
                </p>
              </div>
            ) : (
              <div
                className={cn(
                  "mt-4 border border-dashed border-border bg-muted/30 px-4 py-8 text-center",
                  RADIUS.card,
                )}
              >
                <p className={TYPE.cardTitle}>No confidence average yet</p>
                <p className={cn(TYPE.meta, "mt-1")}>
                  A 7-day average appears here once trust summary data is available.
                </p>
              </div>
            )}
            <div className="mt-4 grid grid-cols-2 gap-3 text-sm text-muted-foreground">
              <span className="flex items-center gap-2">
                <Robot className="h-4 w-4 text-primary" weight="duotone" />
                ML models: <span className="font-medium text-foreground">{mlActive ?? "—"}</span>
              </span>
              <span className="flex items-center gap-2">
                <Database className="h-4 w-4 text-primary" weight="duotone" />
                Memories: <span className="font-medium text-foreground">{memoriesCount ?? "—"}</span>
              </span>
            </div>
          </motion.section>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Panel reduced={reduced}>
            <PanelHeader
              icon={Brain}
              title="Insights status"
              href={APP_ROUTES.intelligence}
              linkLabel={`View ${SURFACE_COPY.insights.title}`}
            />
            {hasLearningSnapshot || mlActive != null || memoriesCount != null ? (
              <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                <MiniStat label="AI systems online" value={onlineSystems ?? "—"} />
                <MiniStat label="ML models active" value={mlActive ?? "—"} />
                <MiniStat label="Last learning cycle" value={lastCycleLabel ?? "—"} />
              </div>
            ) : (
              <div
                className={cn(
                  "mt-4 border border-dashed border-primary/30 bg-primary/5 px-4 py-8 text-center",
                  RADIUS.card,
                )}
              >
                <Brain className="mx-auto h-8 w-8 text-primary" weight="duotone" />
                <p className={cn(TYPE.cardTitle, "mt-2")}>{SURFACE_COPY.insightsHealth.warmingTitle}</p>
                <p className={cn(TYPE.meta, "mt-1")}>{SURFACE_COPY.insightsHealth.warmingHint}</p>
              </div>
            )}
          </Panel>

          <Panel reduced={reduced}>
            <PanelHeader
              icon={ChartLineUp}
              title="Learning velocity"
              href={APP_ROUTES.learning}
              linkLabel={SURFACE_COPY.learning.title}
            />
            <div className="mt-4 h-40">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={learningBars} layout="vertical" barSize={18} margin={{ left: 0, right: 8 }}>
                  <XAxis type="number" hide domain={[0, "dataMax"]} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={72}
                    tick={{ fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    formatter={(value: number, _name, entry) => {
                      const target = (entry.payload as { target: number }).target
                      return [`${value} / ${target}`, "Progress"]
                    }}
                  />
                  <Bar dataKey="current" radius={[0, 6, 6, 0]} isAnimationActive={!reduced}>
                    {learningBars.map((entry) => (
                      <Cell key={entry.name} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className={cn(TYPE.bodyMuted, "mt-2")}>
              {hasLearningSnapshot
                ? "Gravitre is capturing query patterns, workflow outcomes, and memory promotion candidates."
                : "Connect tools and run your first workflow — learning accelerates as soon as data flows in."}
              {readyModelCount != null ? (
                <span className="mt-1 block text-foreground">
                  {readyModelCount} model{readyModelCount === 1 ? "" : "s"} ready for training.
                  {learningVelocity ? ` Velocity: ${learningVelocity}.` : ""}
                </span>
              ) : null}
            </p>
          </Panel>

          <Panel reduced={reduced}>
            <PanelHeader
              icon={WarningCircle}
              title="Revenue risk radar"
              href={APP_ROUTES.revenueRisk}
              linkLabel="View all signals"
            />
            {revenueRisks.length === 0 ? (
              <div
                className={cn(
                  "mt-6 border border-dashed border-success/30 bg-success/5 px-4 py-8 text-center",
                  RADIUS.card,
                )}
              >
                <CheckCircle className="mx-auto h-8 w-8 text-success" weight="duotone" />
                <p className={cn(TYPE.cardTitle, "mt-2 text-success")}>No signals this period</p>
                <p className={cn(TYPE.meta, "mt-1")}>No revenue risk items returned by the API.</p>
              </div>
            ) : (
              <ul className="mt-4 space-y-2">
                {revenueRisks.slice(0, 3).map((risk, index) => (
                  <motion.li
                    key={risk.id}
                    initial={reduced ? false : { opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.08 }}
                    className={cn(
                      "border border-border bg-card px-3 py-2 text-sm transition-colors hover:border-destructive/30 hover:bg-destructive/5",
                      RADIUS.tile,
                    )}
                  >
                    <span className="font-medium text-foreground">{risk.title}</span>
                    <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{risk.summary}</p>
                  </motion.li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel reduced={reduced}>
            <PanelHeader
              icon={ChartLineUp}
              title="Predictive operations"
              href={APP_ROUTES.intelligence}
              linkLabel="Explore forecasts"
            />
            {predictiveSummary ? (
              <p className={cn(TYPE.bodyMuted, "mt-4")}>{predictiveSummary}</p>
            ) : (
              <div
                className={cn(
                  "mt-4 border border-dashed border-border bg-muted/30 px-4 py-8 text-center",
                  RADIUS.card,
                )}
              >
                <p className={TYPE.cardTitle}>No forecast summary yet</p>
                <p className={cn(TYPE.meta, "mt-1")}>
                  Workflow success trends and anomaly signals appear here once enough run history
                  exists — no placeholder chart is invented.
                </p>
              </div>
            )}
          </Panel>
        </div>

        {showGettingStarted ? (
          <motion.p variants={item} className={TYPE.meta}>
            Resume setup from{" "}
            <Link href={APP_ROUTES.welcome} className="underline underline-offset-2 hover:text-foreground">
              Getting Started
            </Link>
            .
          </motion.p>
        ) : null}
      </motion.div>
    </div>
  )
}

function ProgressFooter({
  percent,
  caption,
  accent,
}: {
  percent: number
  caption: string
  accent: "info" | "success"
}) {
  return (
    <div>
      <div className={cn("h-1.5 w-full overflow-hidden bg-muted", RADIUS.control)}>
        <motion.div
          className={cn("h-full", accent === "info" ? "bg-info" : "bg-success", RADIUS.control)}
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </div>
      <span className={cn(TYPE.meta, "mt-1 block")}>{caption}</span>
    </div>
  )
}

function MiniStat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className={cn("border border-border bg-background px-3 py-2", RADIUS.tile)}>
      <p className={TYPE.metricLabel}>{label}</p>
      <p className="mt-1 font-semibold text-foreground">{value}</p>
    </div>
  )
}

function Panel({ children, reduced }: { children: React.ReactNode; reduced: boolean }) {
  return (
    <motion.section
      variants={cardVariants}
      whileHover={reduced ? undefined : { y: -2 }}
      className={cn(
        "border border-border bg-card p-5 shadow-sm transition-shadow hover:shadow-md",
        RADIUS.panel,
      )}
    >
      {children}
    </motion.section>
  )
}

function PanelHeader({
  icon: Icon,
  title,
  href,
  linkLabel,
}: {
  icon: React.ComponentType<{ className?: string; weight?: "duotone" | "regular" }>
  title: string
  href: string
  linkLabel: string
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="flex items-center gap-2">
        <Icon className="h-5 w-5 text-primary" weight="duotone" />
        <h3 className={TYPE.cardTitle}>{title}</h3>
      </div>
      <Link
        href={href}
        className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
      >
        {linkLabel}
        <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  )
}
