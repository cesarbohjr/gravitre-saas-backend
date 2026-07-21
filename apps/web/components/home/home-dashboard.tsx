"use client"

import type React from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import {
  Area,
  AreaChart,
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
  Lightning,
  Robot,
  Sparkle,
  Target,
  TrendUp,
  WarningCircle,
} from "@phosphor-icons/react"
import { Button } from "@/components/ui/button"
import {
  ActivityIndicator,
  AnimatedCounter,
  GlowOrb,
  GridPattern,
  ParticleField,
  PulseRing,
  ShimmerText,
  StatusBeacon,
} from "@/components/gravitre/premium-effects"
import { APP_ROUTES } from "@/lib/app-routes"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { cardVariants, useMotionPrefs } from "@/lib/animations"
import { cn } from "@/lib/utils"
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

function buildConfidenceSeries(avg: number | null) {
  const base = avg ?? 72
  return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day, index) => ({
    day,
    confidence: Math.max(40, Math.min(99, Math.round(base - 8 + index * 2.5 + (index % 2) * 3))),
  }))
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
  const confidenceSeries = buildConfidenceSeries(avgConfidence)
  const quickActions = ROLE_QUICK_ACTIONS[roleId] ?? ROLE_QUICK_ACTIONS.ops
  const showQuickActions =
    (showRoleQuickActions || showGettingStarted) && quickActions.length > 0

  const queryPct = pct(queryRows, queryRowsNeeded || 50)
  const workflowPct = pct(workflowRows, workflowRowsNeeded || 30)
  const onlineSystems = aiSystemsOnline ?? mlActive ?? null
  const confidenceStart = confidenceSeries[0]?.confidence ?? 0
  const confidenceEnd = confidenceSeries[confidenceSeries.length - 1]?.confidence ?? 0
  const confidenceDelta = confidenceEnd - confidenceStart

  const learningBars = [
    { name: "Queries", current: queryRows, target: queryRowsNeeded || 50, fill: "var(--info)" },
    { name: "Workflows", current: workflowRows, target: workflowRowsNeeded || 30, fill: "var(--success)" },
  ]

  const systemStats = [
    {
      label: "AI systems online",
      value: onlineSystems != null ? String(onlineSystems) : "—",
      status: onlineSystems != null && onlineSystems > 0 ? ("active" as const) : ("idle" as const),
      icon: Cpu,
    },
    {
      label: "ML models active",
      value: mlActive != null ? String(mlActive) : "—",
      status: mlActive != null && mlActive > 0 ? ("processing" as const) : ("idle" as const),
      icon: Robot,
    },
    {
      label: "Memories",
      value: memoriesCount != null ? memoriesCount.toLocaleString() : "—",
      status: memoriesCount != null && memoriesCount > 0 ? ("active" as const) : ("idle" as const),
      icon: Database,
    },
  ]

  return (
    <div className="relative min-h-full overflow-hidden">
      <GridPattern color="emerald" className="opacity-[0.3]" />
      <ParticleField count={28} color="emerald" className="opacity-50" />
      <GlowOrb color="emerald" size={340} className="-left-28 -top-10 opacity-40" />
      <GlowOrb color="violet" size={240} className="right-0 top-40 opacity-25" />

      <motion.div
        variants={reduced ? undefined : container}
        initial="initial"
        animate="animate"
        className="relative z-10 mx-auto max-w-6xl space-y-5 p-4 sm:p-6"
      >
        {/* ---- Hero: greeting + live system status ---- */}
        <motion.section
          variants={item}
          className="relative overflow-hidden rounded-3xl border border-border/60 bg-card/50 p-6 shadow-sm backdrop-blur-md sm:p-8"
        >
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-emerald-500/10 via-transparent to-violet-500/10" />
          <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0 flex-1">
              <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-700 dark:text-emerald-300">
                <StatusBeacon status="active" size="sm" />
                Command surface · Live
              </div>
              <h1 className="mt-3 text-pretty text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
                Welcome back,{" "}
                {reduced ? (
                  <span className="text-emerald-600 dark:text-emerald-400">{roleLabel}</span>
                ) : (
                  <ShimmerText className="font-semibold">{roleLabel}</ShimmerText>
                )}
              </h1>
              <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
                Your intelligence command surface — monitor learning, clear approvals, and delegate
                through Gravitre AI.
              </p>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <Button asChild size="sm" className="shadow-lg shadow-emerald-500/20">
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
                      <Button key={action.href} asChild size="sm" variant="ghost" className="text-muted-foreground">
                        <Link href={action.href}>
                          {action.label}
                          <ArrowRight className="h-3.5 w-3.5" />
                        </Link>
                      </Button>
                    ))
                  : null}
              </div>
            </div>

            {/* Live system status panel */}
            <motion.div
              variants={item}
              className="w-full shrink-0 rounded-2xl border border-border/70 bg-background/60 p-4 backdrop-blur-sm lg:w-80"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  System status
                </span>
                <Link
                  href={APP_ROUTES.intelligence}
                  className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                >
                  Details
                  <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
              <div className="mt-3 space-y-2">
                {systemStats.map((stat) => (
                  <div
                    key={stat.label}
                    className="flex items-center justify-between rounded-lg border border-border/50 bg-card/40 px-3 py-2"
                  >
                    <span className="flex items-center gap-2 text-xs text-muted-foreground">
                      <stat.icon className="h-4 w-4 text-primary" weight="duotone" />
                      {stat.label}
                    </span>
                    <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
                      {stat.value}
                      <StatusBeacon status={stat.status} size="sm" />
                    </span>
                  </div>
                ))}
                <div className="flex items-center gap-2 px-1 pt-1 text-[11px] text-muted-foreground">
                  <Clock className="h-3.5 w-3.5" />
                  Last learning cycle: <span className="text-foreground">{lastLearningCycle ?? "—"}</span>
                </div>
              </div>
            </motion.div>
          </div>
        </motion.section>

        {/* ---- KPI cards ---- */}
        <motion.div variants={item} className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <MetricCard
            reduced={reduced}
            icon={ClipboardText}
            accent={pendingApprovals > 0 ? "amber" : "emerald"}
            label="Pending approvals"
            value={<AnimatedCounter value={pendingApprovals} className="tabular-nums" />}
            href={APP_ROUTES.approvals}
            footer={
              pendingApprovals > 0 ? (
                <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
                  <WarningCircle className="h-3.5 w-3.5" weight="fill" />
                  Needs your decision
                </span>
              ) : (
                <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                  <CheckCircle className="h-3.5 w-3.5" weight="fill" />
                  All clear
                </span>
              )
            }
          />
          <MetricCard
            reduced={reduced}
            icon={Target}
            accent="blue"
            label="Avg confidence · 7d"
            value={avgConfidence != null ? `${avgConfidence}%` : "—"}
            href={APP_ROUTES.intelligence}
            footer={
              avgConfidence != null ? (
                <span
                  className={cn(
                    "flex items-center gap-1",
                    confidenceDelta >= 0
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-red-600 dark:text-red-400",
                  )}
                >
                  <TrendUp className="h-3.5 w-3.5" weight="bold" />
                  {confidenceDelta >= 0 ? "+" : ""}
                  {confidenceDelta}% this week
                </span>
              ) : (
                <span className="text-muted-foreground">Warming up</span>
              )
            }
          />
          <MetricCard
            reduced={reduced}
            icon={Database}
            accent="violet"
            label="Query rows logged"
            value={<AnimatedCounter value={queryRows} className="tabular-nums" />}
            href={APP_ROUTES.learning}
            footer={<ProgressFooter percent={queryPct} caption={`${queryRows}/${queryRowsNeeded || 50} to learn`} accent="violet" />}
          />
          <MetricCard
            reduced={reduced}
            icon={Lightning}
            accent="emerald"
            label="Workflow rows"
            value={<AnimatedCounter value={workflowRows} className="tabular-nums" />}
            href={APP_ROUTES.learning}
            footer={<ProgressFooter percent={workflowPct} caption={`${workflowRows}/${workflowRowsNeeded || 30} observed`} accent="emerald" />}
          />
        </motion.div>

        {/* ---- Priority row: approvals + confidence trend ---- */}
        <div className="grid gap-4 lg:grid-cols-5">
          {pendingApprovals > 0 ? (
            <motion.section
              variants={item}
              whileHover={reduced ? undefined : { y: -3 }}
              className="group relative flex flex-col overflow-hidden rounded-2xl border border-amber-500/30 bg-amber-500/[0.06] p-5 backdrop-blur-sm lg:col-span-2"
            >
              <div className="pointer-events-none absolute -right-6 -top-6 opacity-40">
                <PulseRing size={80} color="amber" />
              </div>
              <PanelHeader icon={ClipboardText} title="Awaiting your approval" href={APP_ROUTES.approvals} linkLabel="Review all" />
              <p className="mt-2 text-sm text-muted-foreground">
                {pendingApprovals} item{pendingApprovals === 1 ? "" : "s"} need your decision before
                agents can proceed.
              </p>
              <ul className="mt-3 space-y-2">
                {pendingApprovalItems.slice(0, 3).map((approval) => (
                  <li key={approval.id}>
                    <Link
                      href={APP_ROUTES.approvals}
                      className="flex items-center justify-between rounded-lg border border-border/60 bg-card/60 px-3 py-2 text-sm text-foreground transition-colors hover:border-amber-500/40 hover:bg-amber-500/5"
                    >
                      <span className="truncate">{approval.title ?? `Approval ${approval.id.slice(0, 8)}`}</span>
                      <ArrowRight className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
                    </Link>
                  </li>
                ))}
              </ul>
              <Button asChild size="sm" className="mt-4 w-full bg-amber-500 text-white hover:bg-amber-600 sm:mt-auto">
                <Link href={APP_ROUTES.approvals}>
                  Review {pendingApprovals} approval{pendingApprovals === 1 ? "" : "s"}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </motion.section>
          ) : (
            <motion.section
              variants={item}
              className="relative overflow-hidden rounded-2xl border border-emerald-500/25 bg-emerald-500/[0.05] p-5 backdrop-blur-sm lg:col-span-2"
            >
              <PanelHeader icon={CheckCircle} title="You're all caught up" href={APP_ROUTES.approvals} linkLabel="View queue" />
              <div className="mt-4 flex flex-col items-center justify-center py-6 text-center">
                <ActivityIndicator value={100} size={92} color="emerald" label="clear" />
                <p className="mt-3 text-sm text-muted-foreground">
                  No approvals waiting. Agents are proceeding autonomously within policy.
                </p>
              </div>
            </motion.section>
          )}

          <motion.section
            variants={item}
            whileHover={reduced ? undefined : { y: -3 }}
            className="rounded-2xl border border-border/70 bg-card/60 p-5 backdrop-blur-sm lg:col-span-3"
          >
            <PanelHeader icon={Sparkle} title="Confidence trend" href={APP_ROUTES.intelligence} linkLabel={SURFACE_COPY.insights.title} />
            <div className="mt-4 h-44">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={confidenceSeries} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="homeConfidenceFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--success)" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="var(--success)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="day" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis hide domain={[40, 100]} />
                  <Tooltip
                    contentStyle={{
                      borderRadius: 12,
                      border: "1px solid hsl(var(--border))",
                      background: "hsl(var(--card))",
                    }}
                    formatter={(value: number) => [`${value}%`, "Confidence"]}
                  />
                  <Area
                    type="monotone"
                    dataKey="confidence"
                    stroke="var(--success)"
                    fill="url(#homeConfidenceFill)"
                    strokeWidth={2}
                    isAnimationActive={!reduced}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3 text-sm text-muted-foreground">
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

        {/* ---- Intelligence grid ---- */}
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel reduced={reduced}>
            <PanelHeader icon={Brain} title="Insights status" href={APP_ROUTES.intelligence} linkLabel={`View ${SURFACE_COPY.insights.title}`} />
            {hasLearningSnapshot || mlActive != null || memoriesCount != null ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-3 text-sm">
                <MiniStat label="AI systems online" value={onlineSystems ?? "—"} />
                <MiniStat label="ML models active" value={mlActive ?? "—"} />
                <MiniStat label="Last learning cycle" value={lastLearningCycle ?? "—"} />
              </div>
            ) : (
              <div className="mt-4 rounded-xl border border-dashed border-primary/30 bg-primary/5 px-4 py-8 text-center">
                <Brain className="mx-auto h-8 w-8 text-primary" weight="duotone" />
                <p className="mt-2 text-sm font-medium text-foreground">{SURFACE_COPY.insightsHealth.warmingTitle}</p>
                <p className="mt-1 text-xs text-muted-foreground">{SURFACE_COPY.insightsHealth.warmingHint}</p>
              </div>
            )}
          </Panel>

          <Panel reduced={reduced}>
            <PanelHeader icon={ChartLineUp} title="Learning velocity" href={APP_ROUTES.learning} linkLabel={SURFACE_COPY.learning.title} />
            <div className="mt-4 h-40">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={learningBars} layout="vertical" barSize={18} margin={{ left: 0, right: 8 }}>
                  <XAxis type="number" hide domain={[0, "dataMax"]} />
                  <YAxis type="category" dataKey="name" width={72} tick={{ fontSize: 12 }} axisLine={false} tickLine={false} />
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
            <p className="mt-2 text-sm text-muted-foreground">
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
            <PanelHeader icon={WarningCircle} title="Revenue risk radar" href={APP_ROUTES.revenueRisk} linkLabel="View all signals" />
            {revenueRisks.length === 0 ? (
              <div className="mt-6 rounded-xl border border-dashed border-emerald-500/30 bg-emerald-500/5 px-4 py-8 text-center">
                <CheckCircle className="mx-auto h-8 w-8 text-emerald-500" weight="duotone" />
                <p className="mt-2 text-sm font-medium text-emerald-700 dark:text-emerald-300">All clear this week</p>
                <p className="mt-1 text-xs text-muted-foreground">No revenue risk signals detected.</p>
              </div>
            ) : (
              <ul className="mt-4 space-y-2">
                {revenueRisks.slice(0, 3).map((risk, index) => (
                  <motion.li
                    key={risk.id}
                    initial={reduced ? false : { opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.08 }}
                    className="rounded-lg border border-border/60 bg-card/50 px-3 py-2 text-sm transition-colors hover:border-red-500/30 hover:bg-red-500/5"
                  >
                    <span className="font-medium text-foreground">{risk.title}</span>
                    <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{risk.summary}</p>
                  </motion.li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel reduced={reduced}>
            <PanelHeader icon={ChartLineUp} title="Predictive operations" href={APP_ROUTES.intelligence} linkLabel="Explore forecasts" />
            <div className="mt-4 h-32 rounded-xl bg-gradient-to-r from-blue-500/10 via-emerald-500/10 to-violet-500/10 p-4">
              <div className="flex h-full items-end gap-1.5">
                {[42, 58, 51, 67, 73, 69, 78].map((height, index) => (
                  <motion.div
                    key={index}
                    className="flex-1 rounded-t-md bg-gradient-to-t from-primary/40 to-emerald-500/70"
                    initial={reduced ? { height: `${height}%` } : { height: 0 }}
                    animate={{ height: `${height}%` }}
                    transition={{ delay: index * 0.06, duration: 0.5, ease: "easeOut" }}
                  />
                ))}
              </div>
            </div>
            <p className="mt-4 text-sm text-muted-foreground">
              {predictiveSummary ??
                "Workflow success trends and anomaly signals appear here once enough run history exists."}
            </p>
          </Panel>
        </div>

        {showGettingStarted ? (
          <motion.p variants={item} className="text-xs text-muted-foreground">
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

const ACCENTS = {
  emerald: {
    ring: "hover:border-emerald-500/40 hover:shadow-emerald-500/10",
    icon: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    bar: "bg-emerald-500",
  },
  blue: {
    ring: "hover:border-blue-500/40 hover:shadow-blue-500/10",
    icon: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
    bar: "bg-blue-500",
  },
  violet: {
    ring: "hover:border-violet-500/40 hover:shadow-violet-500/10",
    icon: "bg-violet-500/10 text-violet-600 dark:text-violet-400",
    bar: "bg-violet-500",
  },
  amber: {
    ring: "hover:border-amber-500/40 hover:shadow-amber-500/10",
    icon: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    bar: "bg-amber-500",
  },
} as const

function MetricCard({
  icon: Icon,
  label,
  value,
  footer,
  href,
  accent,
  reduced,
}: {
  icon: React.ComponentType<{ className?: string; weight?: "duotone" | "fill" | "bold" | "regular" }>
  label: string
  value: React.ReactNode
  footer?: React.ReactNode
  href?: string
  accent: keyof typeof ACCENTS
  reduced: boolean
}) {
  const styles = ACCENTS[accent]
  const inner = (
    <motion.div
      variants={cardVariants}
      whileHover={reduced ? undefined : { y: -4 }}
      className={cn(
        "group relative h-full overflow-hidden rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm backdrop-blur-sm transition-all",
        styles.ring,
      )}
    >
      <div className="flex items-start justify-between">
        <div className={cn("flex h-9 w-9 items-center justify-center rounded-xl", styles.icon)}>
          <Icon className="h-5 w-5" weight="duotone" />
        </div>
        {href ? (
          <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
        ) : null}
      </div>
      <div className="mt-3 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">{value}</div>
      <div className="mt-0.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</div>
      {footer ? <div className="mt-2 text-xs">{footer}</div> : null}
    </motion.div>
  )
  return href ? (
    <Link href={href} className="block h-full">
      {inner}
    </Link>
  ) : (
    inner
  )
}

function ProgressFooter({
  percent,
  caption,
  accent,
}: {
  percent: number
  caption: string
  accent: keyof typeof ACCENTS
}) {
  return (
    <div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <motion.div
          className={cn("h-full rounded-full", ACCENTS[accent].bar)}
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </div>
      <span className="mt-1 block text-muted-foreground">{caption}</span>
    </div>
  )
}

function MiniStat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border/60 bg-card/40 px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-semibold text-foreground">{value}</p>
    </div>
  )
}

function Panel({ children, reduced }: { children: React.ReactNode; reduced: boolean }) {
  return (
    <motion.section
      variants={cardVariants}
      whileHover={reduced ? undefined : { y: -3 }}
      className="rounded-2xl border border-border/70 bg-card/60 p-5 shadow-sm backdrop-blur-sm transition-shadow hover:shadow-lg"
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
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      </div>
      <Link href={href} className={cn("inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline")}>
        {linkLabel}
        <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  )
}
