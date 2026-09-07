"use client"

/**
 * Authenticated home command surface — Nodus-inspired light SaaS layout.
 * Real metrics and props only; no fabricated sparklines, agent names, or badges.
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
import { Button } from "@/components/ui/button"
import {
  AnimatedCounter,
} from "@/components/gravitre/premium-effects"
import { APP_ROUTES } from "@/lib/app-routes"
import { relativeTime } from "@/lib/agent-job-result"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { cardVariants, useMotionPrefs } from "@/lib/animations"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { StatusChip } from "@/components/gravitre/visual"
import { GravitreMetric, GravitreSurface } from "@/components/gravitre/nodus-product/metric"
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
  /** Live agent counts — null when list unavailable (honest dash). */
  activeAgents?: number | null
  agentTotal?: number | null
  agentStatusCounts?: {
    active: number
    idle: number
    processing: number
    error: number
  } | null
  /** Verified run success rate % — null when no runs. */
  successRate?: number | null
  avgDurationMs?: number | null
  runsByDay?: Array<{ date: string; count: number }>
  activeWorkflows?: number | null
}

function formatDuration(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms) || ms < 0) return "—"
  if (ms < 1000) return `${Math.round(ms)}ms`
  const seconds = ms / 1000
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const minutes = seconds / 60
  return `${minutes.toFixed(1)}m`
}

function pct(current: number, needed: number) {
  if (!needed || needed <= 0) return current > 0 ? 100 : 0
  return Math.max(0, Math.min(100, Math.round((current / needed) * 100)))
}

const BRAND = "#16a374"
const BRAND_SOFT = "#5ec49a"

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
  activeAgents = null,
  agentTotal = null,
  agentStatusCounts = null,
  successRate = null,
  avgDurationMs = null,
  runsByDay = [],
  activeWorkflows = null,
}: HomeDashboardProps) {
  const { reduced, container, item } = useMotionPrefs()
  const quickActions = ROLE_QUICK_ACTIONS[roleId] ?? ROLE_QUICK_ACTIONS.ops
  const showQuickActions =
    (showRoleQuickActions || showGettingStarted) && quickActions.length > 0

  const queryPct = pct(queryRows, queryRowsNeeded || 50)
  const workflowPct = pct(workflowRows, workflowRowsNeeded || 30)
  const onlineSystems = aiSystemsOnline ?? mlActive ?? null
  const lastCycleLabel = lastLearningCycle ? relativeTime(lastLearningCycle) : null

  const learningBars =
    runsByDay.length > 0
      ? runsByDay.slice(-7).map((day) => ({
          name: day.date.slice(5),
          current: day.count,
          target: Math.max(...runsByDay.map((d) => d.count), 1),
          fill: BRAND,
        }))
      : [
          { name: "Queries", current: queryRows, target: queryRowsNeeded || 50, fill: BRAND },
          { name: "Workflows", current: workflowRows, target: workflowRowsNeeded || 30, fill: BRAND_SOFT },
        ]

  const systemStats = agentStatusCounts
    ? [
        {
          label: "Active",
          value: agentStatusCounts.active,
          display: String(agentStatusCounts.active),
          known: true,
          icon: Robot,
          tone: "brand" as const,
        },
        {
          label: "Processing",
          value: agentStatusCounts.processing,
          display: String(agentStatusCounts.processing),
          known: true,
          icon: Cpu,
          tone: "brandSoft" as const,
        },
        {
          label: "Idle",
          value: agentStatusCounts.idle,
          display: String(agentStatusCounts.idle),
          known: true,
          icon: Clock,
          tone: "muted" as const,
        },
        {
          label: "Error",
          value: agentStatusCounts.error,
          display: String(agentStatusCounts.error),
          known: true,
          icon: WarningCircle,
          tone: "muted" as const,
        },
      ]
    : [
        {
          label: "AI systems online",
          value: onlineSystems != null ? onlineSystems : null,
          display: onlineSystems != null ? String(onlineSystems) : "—",
          known: onlineSystems != null,
          icon: Cpu,
          tone: "brand" as const,
        },
        {
          label: "ML models active",
          value: mlActive != null ? mlActive : null,
          display: mlActive != null ? String(mlActive) : "—",
          known: mlActive != null,
          icon: Robot,
          tone: "brandSoft" as const,
        },
        {
          label: "Memories",
          value: memoriesCount != null ? memoriesCount : null,
          display: memoriesCount != null ? memoriesCount.toLocaleString() : "—",
          known: memoriesCount != null,
          icon: Database,
          tone: "muted" as const,
        },
      ]

  const knownSystemTotal = systemStats
    .filter((s) => s.known && s.value != null)
    .reduce((sum, s) => sum + (s.value as number), 0)

  type ActivityRow = {
    id: string
    item: string
    status: "Pending" | "Online" | "Active" | "Idle" | "Clear"
    detail: string
    href: string
    tone: "warning" | "success" | "idle"
  }

  const activityRows: ActivityRow[] =
    pendingApprovals > 0
      ? [
          ...pendingApprovalItems.slice(0, 5).map((approval) => ({
            id: approval.id,
            item: approval.title ?? `Approval ${approval.id.slice(0, 8)}`,
            status: "Pending" as const,
            detail: "Needs your decision",
            href: APP_ROUTES.approvals,
            tone: "warning" as const,
          })),
          ...(pendingApprovalItems.length === 0
            ? [
                {
                  id: "pending-count",
                  item: `${pendingApprovals} pending approval${pendingApprovals === 1 ? "" : "s"}`,
                  status: "Pending" as const,
                  detail: "Open the approvals queue",
                  href: APP_ROUTES.approvals,
                  tone: "warning" as const,
                },
              ]
            : []),
        ]
      : [
          {
            id: "approvals-clear",
            item: "Approvals",
            status: "Clear" as const,
            detail: "No items waiting",
            href: APP_ROUTES.approvals,
            tone: "success" as const,
          },
          {
            id: "ai-systems",
            item: "AI systems online",
            status: (onlineSystems != null && onlineSystems > 0 ? "Online" : "Idle") as
              | "Online"
              | "Idle",
            detail: onlineSystems != null ? String(onlineSystems) : "—",
            href: APP_ROUTES.intelligence,
            tone: (onlineSystems != null && onlineSystems > 0 ? "success" : "idle") as
              | "success"
              | "idle",
          },
          {
            id: "ml-models",
            item: "ML models active",
            status: (mlActive != null && mlActive > 0 ? "Active" : "Idle") as "Active" | "Idle",
            detail: mlActive != null ? String(mlActive) : "—",
            href: APP_ROUTES.intelligence,
            tone: (mlActive != null && mlActive > 0 ? "success" : "idle") as "success" | "idle",
          },
          {
            id: "memories",
            item: "Memories",
            status: (memoriesCount != null && memoriesCount > 0 ? "Active" : "Idle") as
              | "Active"
              | "Idle",
            detail:
              memoriesCount != null ? memoriesCount.toLocaleString() : "—",
            href: APP_ROUTES.intelligence,
            tone: (memoriesCount != null && memoriesCount > 0 ? "success" : "idle") as
              | "success"
              | "idle",
          },
        ]

  const kpiCards = [
    {
      key: "agents",
      label: "Active agents",
      value:
        activeAgents != null ? (
          <AnimatedCounter value={activeAgents} className="tabular-nums" />
        ) : (
          "—"
        ),
      href: APP_ROUTES.agents,
      icon: <Robot className="h-4 w-4" weight="duotone" />,
      warning: false,
      hint:
        agentTotal != null
          ? `${activeAgents ?? 0} active · ${agentTotal} total →`
          : "Connect agents to populate →",
    },
    {
      key: "success",
      label: "Task success rate",
      value: successRate != null ? `${successRate}%` : "—",
      href: APP_ROUTES.runs,
      icon: <CheckCircle className="h-4 w-4" weight="duotone" />,
      warning: false,
      hint: successRate != null ? "Verified runs →" : "No runs yet →",
    },
    {
      key: "duration",
      label: "Average execution time",
      value: formatDuration(avgDurationMs),
      href: APP_ROUTES.runs,
      icon: <Clock className="h-4 w-4" weight="duotone" />,
      warning: false,
      hint: avgDurationMs != null ? "Mean run duration →" : "Waiting for runs →",
    },
    {
      key: "workflows-active",
      label: "Active workflows",
      value:
        activeWorkflows != null ? (
          <AnimatedCounter value={activeWorkflows} className="tabular-nums" />
        ) : pendingApprovals > 0 ? (
          <AnimatedCounter value={pendingApprovals} className="tabular-nums" />
        ) : (
          "—"
        ),
      href: pendingApprovals > 0 ? APP_ROUTES.approvals : APP_ROUTES.workflows,
      icon:
        pendingApprovals > 0 ? (
          <ClipboardText className="h-4 w-4" weight="duotone" />
        ) : (
          <ChartLineUp className="h-4 w-4" weight="duotone" />
        ),
      warning: pendingApprovals > 0,
      hint:
        pendingApprovals > 0
          ? `${pendingApprovals} pending approval${pendingApprovals === 1 ? "" : "s"} →`
          : activeWorkflows != null
            ? "Live workflow count →"
            : "No active workflows →",
    },
  ]

  return (
    <div className="relative w-full overflow-x-hidden bg-[color:var(--g-canvas)]">
      <motion.div
        variants={reduced ? undefined : container}
        initial="initial"
        animate="animate"
        className="relative z-10 mx-auto max-w-[1400px] space-y-4 px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)] sm:pb-6"
      >
        {/* Header */}
        <motion.header variants={item} className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0 space-y-1">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              Dashboard
            </h1>
            <p className="text-sm text-muted-foreground">
              Welcome back, {roleLabel}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
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
          </div>
        </motion.header>

        {/* Status chips — real API-backed values only */}
        <motion.div variants={item} className="flex flex-wrap items-center gap-2">
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
          <span className={cn(TYPE.meta, "inline-flex items-center gap-1.5")}>
            <Clock className="h-3.5 w-3.5" />
            Last learning cycle:{" "}
            <span className="text-foreground">{lastCycleLabel ?? "—"}</span>
          </span>
        </motion.div>

        {/* KPI row — Nodus Product Image hierarchy, live Gravitre fields */}
        <motion.section
          variants={item}
          className="grid grid-cols-1 gap-[var(--np-kpi-gap)] sm:grid-cols-2 lg:grid-cols-4"
        >
          {kpiCards.map((card) => (
            <GravitreMetric
              key={card.key}
              label={card.label}
              value={card.value}
              hint={card.hint}
              href={card.href}
              icon={card.icon}
              warning={card.warning}
            />
          ))}
        </motion.section>

        {/* Learning progress toward targets */}
        <motion.div variants={item} className="grid gap-[var(--np-kpi-gap)] sm:grid-cols-2">
          <GravitreSurface padded={false} className="px-4 py-3">
            <ProgressFooter
              percent={queryPct}
              caption="Query progress toward learning target"
              accent="brand"
            />
          </GravitreSurface>
          <GravitreSurface padded={false} className="px-4 py-3">
            <ProgressFooter
              percent={workflowPct}
              caption="Workflow progress toward observed target"
              accent="brandSoft"
            />
          </GravitreSurface>
        </motion.div>

        {/* Workflow monitor — Nodus table grammar, real operational rows */}
        <motion.section variants={item}>
          <GravitreSurface>
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-foreground">Workflow monitor</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {pendingApprovals > 0
                  ? "Pending approvals from your queue"
                  : "Live system status from API data"}
              </p>
            </div>
            <Link
              href={pendingApprovals > 0 ? APP_ROUTES.approvals : APP_ROUTES.intelligence}
              className="inline-flex items-center gap-1 text-xs font-medium text-[color:var(--brand)] hover:underline"
            >
              {pendingApprovals > 0 ? "Review all" : "Details"}
              <ArrowRight className="h-3 w-3" />
            </Link>
          </div>

          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[420px] text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs text-muted-foreground">
                  <th className="pb-2 pr-4 font-medium">Item</th>
                  <th className="pb-2 pr-4 font-medium">Status</th>
                  <th className="pb-2 font-medium">Detail</th>
                </tr>
              </thead>
              <tbody>
                {activityRows.map((row) => (
                  <tr key={row.id} className="border-b border-border/60 last:border-0">
                    <td className="py-3 pr-4">
                      <Link
                        href={row.href}
                        className="font-medium text-foreground hover:underline"
                      >
                        {row.item}
                      </Link>
                    </td>
                    <td className="py-3 pr-4">
                      <span className="inline-flex items-center gap-1.5">
                        <span
                          className={cn(
                            "h-1.5 w-1.5 rounded-full",
                            row.tone === "warning" && "bg-amber-500",
                            row.tone === "success" && "bg-[color:var(--brand)]",
                            row.tone === "idle" && "bg-muted-foreground/40",
                          )}
                        />
                        <span
                          className={cn(
                            "text-xs font-medium",
                            row.tone === "warning" && "text-amber-700",
                            row.tone === "success" && "text-foreground",
                            row.tone === "idle" && "text-muted-foreground",
                          )}
                        >
                          {row.status}
                        </span>
                      </span>
                    </td>
                    <td className="py-3 text-xs text-muted-foreground">{row.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </GravitreSurface>
        </motion.section>

        {/* Bottom row: agents/status donut + runs / learning bars */}
        <div className="grid gap-[var(--np-kpi-gap)] lg:grid-cols-2">
          <motion.section variants={item}>
            <GravitreSurface>
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-base font-semibold text-foreground">
                {agentStatusCounts ? "Agents by status" : "Status breakdown"}
              </h2>
              <Link
                href={agentStatusCounts ? APP_ROUTES.agents : APP_ROUTES.intelligence}
                className="inline-flex items-center gap-1 text-xs font-medium text-[color:var(--brand)] hover:underline"
              >
                {agentStatusCounts ? "View agents" : SURFACE_COPY.insights.title}
                <ArrowRight className="h-3 w-3" />
              </Link>
            </div>

            {agentStatusCounts ||
            hasLearningSnapshot ||
            mlActive != null ||
            memoriesCount != null ||
            onlineSystems != null ? (
              <div className="mt-5 flex flex-col gap-6 sm:flex-row sm:items-center">
                {/* Simple ring progress using known totals */}
                <div className="relative mx-auto flex h-36 w-36 shrink-0 items-center justify-center sm:mx-0">
                  <svg viewBox="0 0 36 36" className="h-full w-full -rotate-90">
                    <circle
                      cx="18"
                      cy="18"
                      r="14"
                      fill="none"
                      className="stroke-muted"
                      strokeWidth="3.5"
                    />
                    {systemStats.map((stat, index) => {
                      if (!stat.known || stat.value == null || knownSystemTotal <= 0) return null
                      const share = (stat.value / knownSystemTotal) * 100
                      const circumference = 2 * Math.PI * 14
                      const dash = (share / 100) * circumference
                      let offset = 0
                      for (let i = 0; i < index; i++) {
                        const prev = systemStats[i]
                        if (prev.known && prev.value != null && knownSystemTotal > 0) {
                          offset += (prev.value / knownSystemTotal) * circumference
                        }
                      }
                      const stroke =
                        stat.tone === "brand"
                          ? BRAND
                          : stat.tone === "brandSoft"
                            ? BRAND_SOFT
                            : "#94a3b8"
                      return (
                        <circle
                          key={stat.label}
                          cx="18"
                          cy="18"
                          r="14"
                          fill="none"
                          stroke={stroke}
                          strokeWidth="3.5"
                          strokeDasharray={`${dash} ${circumference - dash}`}
                          strokeDashoffset={-offset}
                          strokeLinecap="butt"
                        />
                      )
                    })}
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                    <span className="text-xl font-semibold tabular-nums text-foreground">
                      {knownSystemTotal > 0 ? knownSystemTotal : "—"}
                    </span>
                    <span className="text-[10px] text-muted-foreground">Tracked</span>
                  </div>
                </div>

                <ul className="flex-1 space-y-3">
                  {systemStats.map((stat) => (
                    <li key={stat.label} className="flex items-center justify-between gap-3">
                      <span className="flex items-center gap-2 text-sm text-muted-foreground">
                        <span
                          className={cn(
                            "h-2 w-2 rounded-full",
                            stat.tone === "brand" && "bg-[color:var(--brand)]",
                            stat.tone === "brandSoft" && "bg-[#5ec49a]",
                            stat.tone === "muted" && "bg-slate-400",
                          )}
                        />
                        <stat.icon className="h-3.5 w-3.5 text-muted-foreground" weight="duotone" />
                        {stat.label}
                      </span>
                      <span className="text-sm font-semibold tabular-nums text-foreground">
                        {stat.display}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="mt-4 rounded-xl border border-dashed border-primary/30 bg-primary/5 px-4 py-8 text-center">
                <Brain className="mx-auto h-8 w-8 text-primary" weight="duotone" />
                <p className={cn(TYPE.cardTitle, "mt-2")}>{SURFACE_COPY.insightsHealth.warmingTitle}</p>
                <p className={cn(TYPE.meta, "mt-1")}>{SURFACE_COPY.insightsHealth.warmingHint}</p>
              </div>
            )}
            </GravitreSurface>
          </motion.section>

          <motion.section variants={item}>
            <GravitreSurface>
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-base font-semibold text-foreground">
                {runsByDay.length > 0 ? "Runs · past 7 days" : "Learning velocity"}
              </h2>
              <Link
                href={runsByDay.length > 0 ? APP_ROUTES.runs : APP_ROUTES.learning}
                className="inline-flex items-center gap-1 text-xs font-medium text-[color:var(--brand)] hover:underline"
              >
                {runsByDay.length > 0 ? "View runs" : SURFACE_COPY.learning.title}
                <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
            <div className="mt-4 h-44">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={learningBars} layout="vertical" barSize={20} margin={{ left: 0, right: 8 }}>
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
              {runsByDay.length > 0
                ? "Daily run counts from metrics overview — no synthetic series."
                : hasLearningSnapshot
                  ? "Gravitre is capturing query patterns, workflow outcomes, and memory promotion candidates."
                  : "Connect tools and run your first workflow — learning accelerates as soon as data flows in."}
              {readyModelCount != null ? (
                <span className="mt-1 block text-foreground">
                  {readyModelCount} model{readyModelCount === 1 ? "" : "s"} ready for training.
                  {learningVelocity ? ` Velocity: ${learningVelocity}.` : ""}
                </span>
              ) : null}
            </p>
            </GravitreSurface>
          </motion.section>
        </div>

        {/* Secondary panels: revenue risks + predictive */}
        <div className="grid gap-[var(--np-kpi-gap)] lg:grid-cols-2">
          <Panel reduced={reduced}>
            <PanelHeader
              icon={WarningCircle}
              title="Revenue risk radar"
              href={APP_ROUTES.revenueRisk}
              linkLabel="View all signals"
            />
            {revenueRisks.length === 0 ? (
              <div className="mt-6 rounded-xl border border-dashed border-[color:var(--brand)]/30 bg-[color:var(--brand)]/5 px-4 py-8 text-center">
                <CheckCircle className="mx-auto h-8 w-8 text-[color:var(--brand)]" weight="duotone" />
                <p className={cn(TYPE.cardTitle, "mt-2 text-[color:var(--brand)]")}>
                  No signals this period
                </p>
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
                    className="rounded-xl border border-border bg-background px-3 py-2 text-sm transition-colors hover:border-destructive/30 hover:bg-destructive/5"
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
              <div className="mt-4 rounded-xl border border-dashed border-border bg-muted/30 px-4 py-8 text-center">
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
  accent: "brand" | "brandSoft"
}) {
  return (
    <div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <motion.div
          className={cn(
            "h-full rounded-full",
            accent === "brand" ? "bg-[color:var(--brand)]" : "bg-[#5ec49a]",
          )}
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </div>
      <span className={cn(TYPE.meta, "mt-1 block")}>{caption}</span>
    </div>
  )
}

function Panel({ children, reduced }: { children: React.ReactNode; reduced: boolean }) {
  return (
    <motion.section
      variants={cardVariants}
      whileHover={reduced ? undefined : { y: -2 }}
      className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-3 shadow-[var(--np-shadow)] transition-shadow sm:p-4"
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
        <Icon className="h-5 w-5 text-[color:var(--brand)]" weight="duotone" />
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
      </div>
      <Link
        href={href}
        className="inline-flex items-center gap-1 text-xs font-medium text-[color:var(--brand)] hover:underline"
      >
        {linkLabel}
        <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  )
}
