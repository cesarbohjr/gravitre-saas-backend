"use client"

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
  ClipboardText,
  Sparkle,
  WarningCircle,
} from "@phosphor-icons/react"
import { PageHeader, StatCard, StatsGrid } from "@/components/gravitre/page-header"
import { Button } from "@/components/ui/button"
import {
  AnimatedCounter,
  GlowOrb,
  GridPattern,
  ParticleField,
} from "@/components/gravitre/premium-effects"
import { APP_ROUTES } from "@/lib/app-routes"
import { cardVariants, entranceContainer, useMotionPrefs } from "@/lib/animations"
import { cn } from "@/lib/utils"
import type { WelcomeRoleId } from "@/lib/welcome-flow"

type HomeDashboardProps = {
  roleLabel: string
  pendingApprovals: number
  avgConfidence: number | null
  queryRows: number
  queryRowsNeeded: number
  workflowRows: number
  workflowRowsNeeded: number
  hasLearningSnapshot: boolean
  mlActive: number | null
  memoriesCount: number | null
  revenueRisks: Array<{ id: string; title: string; summary: string }>
  predictiveSummary: string | null
  showGettingStarted: boolean
}

function buildConfidenceSeries(avg: number | null) {
  const base = avg ?? 72
  return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day, index) => ({
    day,
    confidence: Math.max(40, Math.min(99, Math.round(base - 8 + index * 2.5 + (index % 2) * 3))),
  }))
}

export function HomeDashboard({
  roleLabel,
  pendingApprovals,
  avgConfidence,
  queryRows,
  queryRowsNeeded,
  workflowRows,
  workflowRowsNeeded,
  hasLearningSnapshot,
  mlActive,
  memoriesCount,
  revenueRisks,
  predictiveSummary,
  showGettingStarted,
}: HomeDashboardProps) {
  const { reduced, container } = useMotionPrefs()
  const confidenceSeries = buildConfidenceSeries(avgConfidence)
  const learningBars = [
    {
      name: "Queries",
      current: queryRows,
      target: queryRowsNeeded || 50,
      fill: "var(--success)",
    },
    {
      name: "Workflows",
      current: workflowRows,
      target: workflowRowsNeeded || 30,
      fill: "var(--info)",
    },
  ]

  return (
    <div className="relative min-h-full overflow-hidden">
      <GridPattern color="emerald" className="opacity-[0.35]" />
      <ParticleField count={36} color="emerald" className="opacity-60" />
      <GlowOrb color="emerald" size={320} className="-left-24 top-0 opacity-40" />
      <GlowOrb color="violet" size={220} className="-right-16 top-32 opacity-30" />

      <motion.div
        variants={reduced ? undefined : container}
        initial="initial"
        animate="animate"
        className="relative z-10 mx-auto max-w-6xl space-y-8 p-4 sm:p-6"
      >
        <motion.section variants={cardVariants} className="relative overflow-hidden rounded-2xl border border-border/60 bg-card/40 p-6 backdrop-blur-sm sm:p-8">
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-emerald-500/10 via-transparent to-violet-500/10" />
          <PageHeader
            title={`Welcome back, ${roleLabel}`}
            description="Your intelligence command surface — monitor learning, clear approvals, and delegate through Gravitre AI."
            className="relative border-0 p-0"
            actions={
              <div className="flex flex-wrap gap-2">
                <Button asChild size="sm" className="shadow-lg shadow-emerald-500/20">
                  <Link href={APP_ROUTES.gravitreAi}>Open Gravitre AI</Link>
                </Button>
                {pendingApprovals > 0 ? (
                  <Button asChild size="sm" variant="outline">
                    <Link href={APP_ROUTES.approvals}>
                      {pendingApprovals} approval{pendingApprovals === 1 ? "" : "s"}
                    </Link>
                  </Button>
                ) : null}
              </div>
            }
          />
        </motion.section>

        <motion.div variants={cardVariants}>
          <StatsGrid columns={4}>
            <StatCard
              label="Pending approvals"
              value={
                <AnimatedCounter value={pendingApprovals} className="text-2xl font-semibold" />
              }
              variant={pendingApprovals > 0 ? "warning" : "success"}
            />
            <StatCard
              label="Avg confidence (7d)"
              value={avgConfidence != null ? `${avgConfidence}%` : "—"}
              variant="info"
            />
            <StatCard
              label="Query rows logged"
              value={<AnimatedCounter value={queryRows} className="text-2xl font-semibold" />}
              variant="default"
            />
            <StatCard
              label="Workflow rows"
              value={<AnimatedCounter value={workflowRows} className="text-2xl font-semibold" />}
              variant="default"
            />
          </StatsGrid>
        </motion.div>

        <div className="grid gap-4 lg:grid-cols-2">
          <motion.section
            variants={cardVariants}
            className="rounded-2xl border border-border/70 bg-card/60 p-5 backdrop-blur-sm"
          >
            <PanelHeader icon={Sparkle} title="Confidence trend" href={APP_ROUTES.intelligence} linkLabel="Intelligence Center" />
            <div className="mt-4 h-44">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={confidenceSeries}>
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
            <ul className="mt-4 grid grid-cols-2 gap-3 text-sm text-muted-foreground">
              <li>ML models active: {mlActive ?? "—"}</li>
              <li>Memories accumulated: {memoriesCount ?? "—"}</li>
            </ul>
          </motion.section>

          <motion.section
            variants={cardVariants}
            className="rounded-2xl border border-border/70 bg-card/60 p-5 backdrop-blur-sm"
          >
            <PanelHeader icon={Brain} title="Learning velocity" href={APP_ROUTES.orgLearning} linkLabel="Org Learning" />
            <div className="mt-4 h-44">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={learningBars} layout="vertical" barSize={18}>
                  <XAxis type="number" hide domain={[0, "dataMax"]} />
                  <YAxis type="category" dataKey="name" width={72} tick={{ fontSize: 12 }} axisLine={false} tickLine={false} />
                  <Tooltip
                    formatter={(value: number, _name, item) => {
                      const target = (item.payload as { target: number }).target
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
            <p className="mt-3 text-sm text-muted-foreground">
              {hasLearningSnapshot
                ? "Gravitre is capturing query patterns, workflow outcomes, and memory promotion candidates."
                : "Connect tools and run your first workflow — learning accelerates as soon as data flows in."}
            </p>
          </motion.section>

          <motion.section
            variants={cardVariants}
            className="rounded-2xl border border-border/70 bg-card/60 p-5 backdrop-blur-sm"
          >
            <PanelHeader icon={WarningCircle} title="Revenue risk radar" href={APP_ROUTES.orgLearning} linkLabel="View signals" />
            {revenueRisks.length === 0 ? (
              <div className="mt-6 rounded-xl border border-dashed border-emerald-500/30 bg-emerald-500/5 px-4 py-8 text-center">
                <p className="text-sm font-medium text-emerald-700 dark:text-emerald-300">All clear this week</p>
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
                    className="rounded-lg border border-border/60 px-3 py-2 text-sm"
                  >
                    <span className="font-medium text-foreground">{risk.title}</span>
                    <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{risk.summary}</p>
                  </motion.li>
                ))}
              </ul>
            )}
          </motion.section>

          <motion.section
            variants={cardVariants}
            className="rounded-2xl border border-border/70 bg-card/60 p-5 backdrop-blur-sm"
          >
            <PanelHeader icon={ChartLineUp} title="Predictive operations" href={APP_ROUTES.intelligence} linkLabel="Explore forecasts" />
            <div className="mt-4 h-32 rounded-xl bg-gradient-to-r from-blue-500/10 via-emerald-500/10 to-violet-500/10 p-4">
              <motion.div
                className="flex h-full items-end gap-1"
                initial={reduced ? false : "initial"}
                animate="animate"
              >
                {[42, 58, 51, 67, 73, 69, 78].map((height, index) => (
                  <motion.div
                    key={index}
                    className="flex-1 rounded-t-md bg-gradient-to-t from-primary/40 to-emerald-500/60"
                    initial={reduced ? { height: `${height}%` } : { height: 0 }}
                    animate={{ height: `${height}%` }}
                    transition={{ delay: index * 0.06, duration: 0.5, ease: "easeOut" }}
                  />
                ))}
              </motion.div>
            </div>
            <p className="mt-4 text-sm text-muted-foreground">
              {predictiveSummary ??
                "Workflow success trends and anomaly signals appear here once enough run history exists."}
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
          </motion.section>
        </div>

        {showGettingStarted ? (
          <motion.p variants={cardVariants} className="text-xs text-muted-foreground">
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
