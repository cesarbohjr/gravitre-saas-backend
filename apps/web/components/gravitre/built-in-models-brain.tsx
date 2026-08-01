"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import {
  Brain,
  CircleHelp,
  Database,
  Plus,
  Rocket,
  Sparkles,
  ArrowRight,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"
import { APP_ROUTES } from "@/lib/app-routes"
import { formatScore, modelStatusChipClass } from "@/lib/intelligence/helpers"
import {
  groupBuiltInModels,
  statusLabel,
  statusTone,
  summarizeBrainHealth,
  type BuiltInModelListItem,
} from "@/lib/built-in-model-catalog"

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.04 } },
}

const itemAnim = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0 },
}

function toneAccent(tone: ReturnType<typeof statusTone>): string {
  if (tone === "ready") return "border-emerald-500/25 bg-emerald-500/5"
  if (tone === "learning") return "border-amber-500/25 bg-amber-500/5"
  if (tone === "off") return "border-border/60 bg-muted/20 opacity-80"
  return "border-sky-500/20 bg-sky-500/5"
}

export function BuiltInModelsBrain({
  items,
  filter,
}: {
  items: BuiltInModelListItem[]
  filter: "all" | "active" | "needs_data" | "roadmap"
}) {
  const filtered = items.filter((row) => {
    const tone = statusTone(row.status)
    if (filter === "active") return tone === "ready" || tone === "learning"
    if (filter === "needs_data")
      return (tone === "ready" || tone === "learning") && row.sufficiency.value != null && row.sufficiency.value < 100
    if (filter === "roadmap") return tone === "planned" || tone === "off"
    return true
  })

  const health = summarizeBrainHealth(items)
  const groups = groupBuiltInModels(filtered)

  return (
    <div className="space-y-8">
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="relative overflow-hidden rounded-2xl border border-border/70 bg-gradient-to-br from-card/90 via-card/50 to-emerald-500/5 p-5 sm:p-6"
      >
        <div
          aria-hidden
          className="pointer-events-none absolute -right-14 -top-14 h-44 w-44 rounded-full bg-emerald-500/10 blur-3xl"
        />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-300">
              <motion.span
                animate={{ opacity: [0.45, 1, 0.45] }}
                transition={{ duration: 2.2, repeat: Infinity }}
                className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500"
              />
              Org ML brain
            </div>
            <h2 className="text-balance text-xl font-semibold text-foreground sm:text-2xl">
              Teach Gravitre how your business works
            </h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Built-in models learn from verified signals in your org — chat outcomes, workflow runs,
              CRM and support data. Each model starts weak on rules, then gets sharper once you pass
              its data gate. Past the gate is not a ceiling: more good data keeps improving quality.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs lg:justify-end">
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-2.5 py-1.5 font-medium text-emerald-700 dark:text-emerald-300">
              <Brain className="h-3.5 w-3.5" />
              {health.trained} trained
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-amber-500/20 bg-amber-500/5 px-2.5 py-1.5 font-medium text-amber-700 dark:text-amber-300">
              <Sparkles className="h-3.5 w-3.5" />
              {health.learning} learning
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-sky-500/20 bg-sky-500/5 px-2.5 py-1.5 font-medium text-sky-700 dark:text-sky-300">
              <Database className="h-3.5 w-3.5" />
              {health.collecting} need more data
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-border/70 bg-background/60 px-2.5 py-1.5 font-medium text-muted-foreground">
              {health.readyPct}% of active models trained
            </span>
          </div>
        </div>
      </motion.section>

      <div className="grid gap-3 md:grid-cols-2">
        <aside className="rounded-xl border border-border/70 bg-secondary/20 p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
            <CircleHelp className="h-4 w-4 text-muted-foreground" />
            Why is there a data limit?
          </div>
          <p className="text-sm leading-relaxed text-muted-foreground">
            The bar shows a <span className="font-medium text-foreground">minimum quality gate</span>, not a
            max. Below it, predictions are too noisy to trust. Hitting the number unlocks reliable training;
            going past it still helps. Thresholds are set by Gravitre for model quality — orgs don’t raise or
            lower them from this page.
          </p>
        </aside>
        <aside className="rounded-xl border border-border/70 bg-secondary/20 p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
            <Plus className="h-4 w-4 text-muted-foreground" />
            Can I add new models?
          </div>
          <p className="mb-3 text-sm leading-relaxed text-muted-foreground">
            Built-in catalog models ship with the platform (see Coming capabilities). For your own predictors
            and fine-tunes, use the production model registry.
          </p>
          <div className="flex flex-wrap gap-2">
            <Link
              href={APP_ROUTES.models}
              className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-500/15 dark:text-emerald-300"
            >
              <Rocket className="h-3.5 w-3.5" />
              Open model registry
              <ArrowRight className="h-3 w-3" />
            </Link>
            <Link
              href={APP_ROUTES.training}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border/70 bg-background/70 px-3 py-1.5 text-xs font-medium text-foreground hover:bg-secondary/60"
            >
              Training & data
            </Link>
          </div>
        </aside>
      </div>

      {groups.length === 0 ? (
        <p className="text-sm text-muted-foreground">No models match this filter.</p>
      ) : (
        groups.map(({ domain, items: domainItems }) => (
          <section key={domain.id} className="space-y-3">
            <div className="flex items-end justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-foreground">{domain.title}</h3>
                <p className="text-xs text-muted-foreground">{domain.summary}</p>
              </div>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {domainItems.length} model{domainItems.length === 1 ? "" : "s"}
              </span>
            </div>
            <motion.div
              variants={container}
              initial="hidden"
              animate="show"
              className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3"
            >
              {domainItems.map((row) => {
                const tone = statusTone(row.status)
                return (
                  <motion.div key={row.id} variants={itemAnim}>
                    <Link
                      href={`${APP_ROUTES.builtInModels}/${encodeURIComponent(row.id)}`}
                      className={cn(
                        "group flex h-full flex-col gap-3 rounded-xl border p-4 transition hover:border-foreground/20 hover:bg-card/80",
                        toneAccent(tone),
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 space-y-1">
                          <p className="truncate text-sm font-semibold text-foreground group-hover:underline">
                            {row.guide.label}
                          </p>
                          <p className="font-mono text-[10px] text-muted-foreground/80">{row.id}</p>
                        </div>
                        <Badge variant="outline" className={cn("shrink-0 capitalize", modelStatusChipClass(row.status))}>
                          {statusLabel(row.status)}
                        </Badge>
                      </div>
                      <p className="line-clamp-3 text-xs leading-relaxed text-muted-foreground">
                        {row.guide.summary}
                      </p>
                      <p className="line-clamp-2 text-[11px] leading-relaxed text-foreground/80">
                        <span className="font-medium">Why train: </span>
                        {row.guide.whyItMatters}
                      </p>
                      <div className="mt-auto space-y-1.5 pt-1">
                        {row.sufficiency.value == null ? (
                          <p className="text-[11px] text-muted-foreground">{row.sufficiency.label}</p>
                        ) : (
                          <>
                            <div className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
                              <span>Data toward training gate</span>
                              <span className="tabular-nums">{row.sufficiency.label}</span>
                            </div>
                            <Progress value={row.sufficiency.value} className="h-1.5" />
                            <p className="text-[10px] leading-snug text-muted-foreground">
                              {row.guide.dataExplainer}
                            </p>
                          </>
                        )}
                        <div className="flex items-center justify-between pt-1 text-[11px] text-muted-foreground">
                          <span>Outcome score {formatScore(row.outcomeScore)}</span>
                          <span className="inline-flex items-center gap-1 text-foreground/70 group-hover:text-foreground">
                            Details
                            <ArrowRight className="h-3 w-3 transition group-hover:translate-x-0.5" />
                          </span>
                        </div>
                      </div>
                    </Link>
                  </motion.div>
                )
              })}
            </motion.div>
          </section>
        ))
      )}
    </div>
  )
}
