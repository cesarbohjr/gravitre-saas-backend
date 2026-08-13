"use client"

import useSWR from "swr"
import { motion } from "framer-motion"
import { Badge } from "@/components/ui/badge"
import { intelligenceApi } from "@/lib/api"
import { Gauge, WarningCircle } from "@phosphor-icons/react"
import { cn } from "@/lib/utils"
import { SURFACE_COPY } from "@/lib/surface-copy"

function severityVariant(severity: string): "destructive" | "secondary" | "outline" {
  if (severity === "high") return "destructive"
  if (severity === "medium") return "secondary"
  return "outline"
}

function scoreTone(score: number | null | undefined): string {
  if (score == null) return "text-foreground"
  if (score >= 80) return "text-emerald-600 dark:text-emerald-400"
  if (score >= 60) return "text-amber-600 dark:text-amber-400"
  return "text-rose-600 dark:text-rose-400"
}

function DimensionBar({ label, value, delay }: { label: string; value: number; delay: number }) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium tabular-nums text-foreground">{value}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-secondary/80">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400"
          initial={{ width: 0 }}
          animate={{ width: `${Math.max(0, Math.min(100, value))}%` }}
          transition={{ duration: 0.6, ease: "easeOut", delay }}
        />
      </div>
    </div>
  )
}

export function BusinessImpactCard() {
  const { data, isLoading } = useSWR(
    "admin/intelligence/business-impact",
    () => intelligenceApi.businessImpact(),
    { revalidateOnFocus: false },
  )

  const score = data?.businessImpactScore
  const items = data?.revenueRiskItems ?? []

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="relative overflow-hidden rounded-2xl border border-border/70 bg-gradient-to-br from-card via-card/95 to-emerald-500/[0.06] p-5 shadow-sm"
      >
        <div aria-hidden className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full bg-emerald-500/10 blur-2xl" />
        <div className="relative space-y-4">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 ring-1 ring-emerald-500/20">
              <Gauge className="h-5 w-5 text-emerald-600 dark:text-emerald-400" weight="duotone" aria-hidden />
            </span>
            <div>
              <h3 className="text-base font-semibold text-foreground">{SURFACE_COPY.learningAdmin.businessImpactTitle}</h3>
              <p className="mt-0.5 text-xs text-muted-foreground text-pretty">
                {SURFACE_COPY.learningAdmin.businessImpactHint}
              </p>
            </div>
          </div>

          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <>
              <div className="flex items-end gap-3">
                <span className={cn("text-5xl font-semibold tabular-nums tracking-tight", scoreTone(score))}>
                  {score ?? "—"}
                </span>
                {data?.scoreLabel ? (
                  <Badge variant={score != null && score < 60 ? "destructive" : "secondary"} className="mb-2">
                    {data.scoreLabel.replace("_", " ")}
                  </Badge>
                ) : null}
              </div>

              {data?.dimensions ? (
                <div className="space-y-3 pt-1">
                  <DimensionBar label="Revenue risk" value={data.dimensions.revenueRisk} delay={0.1} />
                  <DimensionBar label="Outcome health" value={data.dimensions.outcomeHealth} delay={0.18} />
                  <DimensionBar label="Operational load" value={data.dimensions.operationalLoad} delay={0.26} />
                </div>
              ) : null}

              <p className="text-[11px] leading-relaxed text-muted-foreground text-pretty">{data?.scopeNote}</p>
            </>
          )}
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.06 }}
        className="relative overflow-hidden rounded-2xl border border-border/70 bg-gradient-to-br from-card via-card/95 to-amber-500/[0.05] p-5 shadow-sm"
      >
        <div aria-hidden className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full bg-amber-500/10 blur-2xl" />
        <div className="relative space-y-4">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-500/10 ring-1 ring-amber-500/20">
              <WarningCircle className="h-5 w-5 text-amber-600 dark:text-amber-400" weight="duotone" aria-hidden />
            </span>
            <div>
              <section id="revenue-risk" className="scroll-mt-24">
                <h3 className="text-base font-semibold text-foreground">{SURFACE_COPY.learningAdmin.revenueRiskTitle}</h3>
                <p className="mt-0.5 text-xs text-muted-foreground text-pretty">
                  Suggestions and outcome signals worth a look before they become costly.
                </p>
              </section>
            </div>
          </div>

          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : items.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border/80 bg-background/50 px-4 py-8 text-center">
              <p className="text-sm font-medium text-foreground">All clear for now</p>
              <p className="mt-1 text-xs text-muted-foreground text-pretty">
                No revenue-risk items pending review. Run optimization detection or wait for more outcome samples.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {items.map((item, index) => (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className="rounded-xl border border-border/70 bg-background/50 p-3 transition-colors hover:border-amber-500/25 hover:bg-background/80"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-sm">{item.title}</span>
                    <Badge variant={severityVariant(item.severity)}>{item.severity}</Badge>
                    <Badge variant="outline">{item.source.replace("_", " ")}</Badge>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">{item.summary}</p>
                  {item.explanation ? (
                    <p className="mt-2 text-xs text-muted-foreground text-pretty">{item.explanation}</p>
                  ) : null}
                </motion.div>
              ))}
            </div>
          )}
        </div>
      </motion.div>
    </div>
  )
}
