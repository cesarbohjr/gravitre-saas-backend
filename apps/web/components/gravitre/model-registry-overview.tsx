"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import {
  Brain,
  Cable,
  Layers,
  LineChart,
  Rocket,
  ShieldAlert,
  Sparkles,
  Workflow,
  ArrowRight,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { APP_ROUTES } from "@/lib/app-routes"
import { SURFACE_COPY } from "@/lib/surface-copy"
import {
  ML_STACK_LAYERS,
  type MlStackLayerId,
} from "@/lib/ml-registry-catalog"
import { MlKnowledgePanel } from "@/components/gravitre/ml-knowledge-panel"

const layerIcons: Record<MlStackLayerId, typeof Brain> = {
  generative: Sparkles,
  classical: Layers,
  timeseries: LineChart,
  anomaly: ShieldAlert,
  mlops: Workflow,
}

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.06 },
  },
}

const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0 },
}

interface ModelRegistryOverviewProps {
  totalModels: number
  deployedCount: number
  trainingCount: number
  connectedDataSources: string[]
  selectedLayer?: MlStackLayerId | null
  onSelectTemplate?: (layerId: MlStackLayerId) => void
}

export function ModelRegistryOverview({
  totalModels,
  deployedCount,
  trainingCount,
  connectedDataSources,
  selectedLayer,
  onSelectTemplate,
}: ModelRegistryOverviewProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className="relative overflow-hidden rounded-2xl border border-border/70 bg-gradient-to-br from-card/80 via-card/40 to-emerald-500/5 p-5 sm:p-6"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-emerald-500/10 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-20 -left-10 h-40 w-40 rounded-full bg-teal-500/10 blur-3xl"
      />

      <div className="relative flex flex-col gap-6">
        {/* Intro row */}
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-300">
              <motion.span
                animate={{ opacity: [0.5, 1, 0.5] }}
                transition={{ duration: 2.4, repeat: Infinity }}
                className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500 dark:bg-emerald-400"
              />
              {SURFACE_COPY.models.badge}
            </div>
            <h2 className="text-balance text-xl font-semibold text-foreground sm:text-2xl">
              {SURFACE_COPY.models.heroTitle}
            </h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Track versions, wire datasets from{" "}
              <Link href={APP_ROUTES.training} className="text-emerald-600 underline-offset-4 hover:underline dark:text-emerald-300">
                {SURFACE_COPY.training.title}
              </Link>
              , and expose inference to workflows. For org-wide signals, see{" "}
              <Link href={APP_ROUTES.learning} className="text-emerald-600 underline-offset-4 hover:underline dark:text-emerald-300">
                {SURFACE_COPY.learning.title}
              </Link>
              .
            </p>
          </div>

          {/* Stat pills */}
          <div className="flex flex-wrap gap-2 text-xs lg:justify-end">
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-2.5 py-1.5 font-medium text-emerald-600 dark:text-emerald-300">
              <Brain className="h-3.5 w-3.5" />
              {totalModels} registered
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-2.5 py-1.5 font-medium text-emerald-600 dark:text-emerald-400">
              <Rocket className="h-3.5 w-3.5" />
              {deployedCount} deployed
            </span>
            {trainingCount > 0 ? (
              <span className="inline-flex items-center gap-1.5 rounded-lg border border-blue-500/20 bg-blue-500/5 px-2.5 py-1.5 font-medium text-blue-600 dark:text-blue-400">
                <Sparkles className="h-3.5 w-3.5" />
                {trainingCount} training
              </span>
            ) : null}
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-teal-500/20 bg-teal-500/5 px-2.5 py-1.5 font-medium text-teal-600 dark:text-teal-400">
              <Cable className="h-3.5 w-3.5" />
              {connectedDataSources.length > 0
                ? `${connectedDataSources.length} data source${connectedDataSources.length === 1 ? "" : "s"}`
                : "Connect data"}
            </span>
          </div>
        </div>

        <MlKnowledgePanel />

        {/* Template grid — full width, organized */}
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Start from a template
            </span>
            <span className="h-px flex-1 bg-border/60" />
          </div>
          <motion.div
            variants={container}
            initial="hidden"
            animate="show"
            className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
          >
            {ML_STACK_LAYERS.map((layer) => {
              const Icon = layerIcons[layer.id]
              const isSelected = selectedLayer === layer.id
              const interactive = Boolean(onSelectTemplate)

              return (
                <motion.button
                  key={layer.id}
                  type="button"
                  variants={item}
                  whileHover={interactive ? { y: -4 } : undefined}
                  whileTap={interactive ? { scale: 0.99 } : undefined}
                  transition={{ type: "spring", stiffness: 320, damping: 24 }}
                  onClick={() => onSelectTemplate?.(layer.id)}
                  disabled={!interactive}
                  className={cn(
                    "group relative overflow-hidden rounded-xl border bg-background/50 p-4 text-left ring-1 backdrop-blur-sm transition-shadow",
                    layer.accent,
                    interactive &&
                      "cursor-pointer hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50",
                    isSelected && "ring-2 ring-emerald-500/60 shadow-md",
                    !interactive && "cursor-default",
                  )}
                >
                  {/* Hover gradient wash */}
                  <span
                    aria-hidden
                    className={cn(
                      "pointer-events-none absolute inset-0 bg-gradient-to-br opacity-0 transition-opacity duration-300 group-hover:opacity-100",
                      layer.accent,
                    )}
                  />
                  <div className="relative">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-background/70 ring-1 ring-border/50 transition-transform duration-300 group-hover:scale-110">
                          <Icon className="h-4 w-4 shrink-0 text-foreground/80" />
                        </span>
                        <p className="text-sm font-semibold text-foreground">{layer.title}</p>
                      </div>
                      {interactive ? (
                        <span className="inline-flex shrink-0 items-center gap-0.5 text-[10px] font-medium text-emerald-600 dark:text-emerald-300">
                          Use
                          <ArrowRight className="h-3 w-3 transition-transform duration-300 group-hover:translate-x-0.5" />
                        </span>
                      ) : null}
                    </div>
                    <p className="text-xs leading-relaxed text-muted-foreground">{layer.summary}</p>
                    <ul className="mt-2.5 space-y-1">
                      {layer.highlights.map((h) => (
                        <li
                          key={h}
                          className="flex items-center gap-1.5 text-[11px] text-muted-foreground/90"
                        >
                          <span className="h-1 w-1 shrink-0 rounded-full bg-muted-foreground/50" />
                          {h}
                        </li>
                      ))}
                    </ul>
                  </div>
                </motion.button>
              )
            })}
          </motion.div>
        </div>
      </div>
    </motion.section>
  )
}
