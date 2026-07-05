"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { BookOpen, Brain, ListChecks, Rocket } from "lucide-react"
import { APP_ROUTES } from "@/lib/app-routes"
import { SURFACE_COPY } from "@/lib/surface-copy"

type TrainingOverviewProps = {
  totalDatasets: number
  readyDatasets: number
  totalJobs: number
  activeJobs: number
  totalInstructions: number
}

export function TrainingOverview({
  totalDatasets,
  readyDatasets,
  totalJobs,
  activeJobs,
  totalInstructions,
}: TrainingOverviewProps) {
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
        className="pointer-events-none absolute -bottom-20 -left-10 h-40 w-40 rounded-full bg-blue-500/10 blur-3xl"
      />

      <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl space-y-3">
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-300">
            <motion.span
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 2.4, repeat: Infinity }}
              className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500"
            />
            {SURFACE_COPY.training.badge}
          </div>
          <h2 className="text-balance text-xl font-semibold text-foreground sm:text-2xl">
            {SURFACE_COPY.training.heroTitle}
          </h2>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Add datasets, run fine-tunes, and assign models to workflow agents. Starts from what{" "}
            <Link href={APP_ROUTES.learning} className="text-emerald-600 underline-offset-4 hover:underline dark:text-emerald-300">
              {SURFACE_COPY.learning.title}
            </Link>{" "}
            already detected. Deploy finished models in{" "}
            <Link href={APP_ROUTES.models} className="text-emerald-600 underline-offset-4 hover:underline dark:text-emerald-300">
              {SURFACE_COPY.models.title}
            </Link>
            .
          </p>
        </div>

        <div className="flex flex-wrap gap-2 text-xs lg:justify-end">
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-2.5 py-1.5 font-medium text-emerald-600 dark:text-emerald-300">
            <BookOpen className="h-3.5 w-3.5" />
            {totalDatasets} datasets
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-2.5 py-1.5 font-medium text-emerald-600 dark:text-emerald-400">
            <ListChecks className="h-3.5 w-3.5" />
            {readyDatasets} ready
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-blue-500/20 bg-blue-500/5 px-2.5 py-1.5 font-medium text-blue-600 dark:text-blue-400">
            <Rocket className="h-3.5 w-3.5" />
            {activeJobs > 0 ? `${activeJobs} active jobs` : `${totalJobs} jobs`}
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-border/70 bg-background/60 px-2.5 py-1.5 font-medium text-muted-foreground">
            <Brain className="h-3.5 w-3.5" />
            {totalInstructions} instructions
          </span>
        </div>
      </div>
    </motion.section>
  )
}
