"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { ArrowRight, Brain, Cpu, Sparkle } from "@phosphor-icons/react"

export type LearningSurfaceId = "org-learning" | "agent-training" | "model-registry"

const SURFACES: Array<{
  id: LearningSurfaceId
  href: string
  title: string
  summary: string
  step: string
  icon: typeof Brain
  accent: string
  ring: string
  glow: string
}> = [
  {
    id: "org-learning",
    href: "/admin/intelligence",
    title: "Org Learning",
    step: "Observe",
    summary: "Automatic learning from queries, memory, and search quality.",
    icon: Sparkle,
    accent: "text-violet-600 dark:text-violet-300",
    ring: "ring-violet-500/25 border-violet-500/30 bg-violet-500/5",
    glow: "from-violet-500/15 to-transparent",
  },
  {
    id: "agent-training",
    href: "/training",
    title: "Agent Training",
    step: "Fine-tune",
    summary: "Datasets, jobs, and custom instructions for agents.",
    icon: Brain,
    accent: "text-emerald-600 dark:text-emerald-300",
    ring: "ring-emerald-500/25 border-emerald-500/30 bg-emerald-500/5",
    glow: "from-emerald-500/15 to-transparent",
  },
  {
    id: "model-registry",
    href: "/models",
    title: "Model Registry",
    step: "Deploy",
    summary: "Register, version, and serve models in workflows.",
    icon: Cpu,
    accent: "text-teal-600 dark:text-teal-300",
    ring: "ring-teal-500/25 border-teal-500/30 bg-teal-500/5",
    glow: "from-teal-500/15 to-transparent",
  },
]

export function LearningSurfacesCallout({
  current,
  className,
  compact = false,
}: {
  current: LearningSurfaceId
  className?: string
  compact?: boolean
}) {
  const currentIndex = SURFACES.findIndex((s) => s.id === current)

  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-2xl border border-border/70 bg-gradient-to-br from-card via-card/95 to-emerald-500/[0.04]",
        compact ? "p-3 sm:p-4" : "p-4 sm:p-5",
        className,
      )}
      aria-label="Learning surfaces navigation"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-emerald-500/10 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-16 -left-12 h-36 w-36 rounded-full bg-violet-500/8 blur-3xl"
      />

      <div className="relative space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Gravitre learning loop
            </p>
            {!compact ? (
              <p className="mt-0.5 text-xs text-muted-foreground text-pretty">
                Three connected surfaces — observe org signals, fine-tune agents, deploy production ML.
              </p>
            ) : null}
          </div>
          <div className="hidden items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground sm:flex">
            {SURFACES.map((surface, index) => (
              <span key={surface.id} className="inline-flex items-center gap-1.5">
                <span className={cn(surface.id === current && "text-emerald-600 dark:text-emerald-400")}>
                  {surface.step}
                </span>
                {index < SURFACES.length - 1 ? (
                  <ArrowRight className="h-3 w-3 opacity-40" aria-hidden />
                ) : null}
              </span>
            ))}
          </div>
        </div>

        <div className="grid gap-2 md:grid-cols-3 md:gap-0">
          {SURFACES.map((surface, index) => {
            const Icon = surface.icon
            const isCurrent = surface.id === current
            const isPast = currentIndex > index
            const isFuture = currentIndex < index

            const card = (
              <motion.div
                layout
                className={cn(
                  "relative flex h-full flex-col rounded-xl border p-3 transition-all md:rounded-none md:border-y md:border-l-0 md:border-r-0 md:first:rounded-l-xl md:first:border-l md:last:rounded-r-xl md:last:border-r",
                  isCurrent
                    ? cn("z-10 shadow-sm ring-1", surface.ring)
                    : "border-border/60 bg-background/40 hover:bg-background/80",
                  !isCurrent && "md:hover:border-emerald-500/20",
                )}
              >
                {isCurrent ? (
                  <div
                    aria-hidden
                    className={cn(
                      "pointer-events-none absolute inset-0 rounded-xl bg-gradient-to-br opacity-80 md:rounded-none md:first:rounded-l-xl md:last:rounded-r-xl",
                      surface.glow,
                    )}
                  />
                ) : null}

                <div className="relative flex items-start gap-2.5">
                  <span
                    className={cn(
                      "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ring-1 ring-inset",
                      isCurrent
                        ? surface.ring
                        : isPast
                          ? "bg-emerald-500/10 ring-emerald-500/20"
                          : "bg-secondary/80 ring-border/60",
                    )}
                  >
                    <Icon
                      className={cn("h-4 w-4", isCurrent ? surface.accent : "text-muted-foreground")}
                      weight="duotone"
                      aria-hidden
                    />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-foreground">{surface.title}</span>
                      {isCurrent ? (
                        <span className="rounded-full bg-foreground px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-background">
                          Active
                        </span>
                      ) : isPast ? (
                        <span className="text-[10px] font-medium text-emerald-600 dark:text-emerald-400">
                          Completed step
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground text-pretty">
                      {surface.summary}
                    </p>
                  </div>
                </div>

                {!isCurrent ? (
                  <Link
                    href={surface.href}
                    className={cn(
                      "relative mt-3 inline-flex items-center gap-1 text-[11px] font-medium transition-colors",
                      isFuture ? "text-primary hover:underline" : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    Open {surface.title}
                    <ArrowRight className="h-3 w-3" aria-hidden />
                  </Link>
                ) : (
                  <p className="relative mt-3 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    You are here · Step {index + 1} of 3
                  </p>
                )}
              </motion.div>
            )

            return (
              <div key={surface.id} className="relative md:flex md:items-stretch">
                {card}
                {index < SURFACES.length - 1 ? (
                  <div
                    aria-hidden
                    className="pointer-events-none absolute right-0 top-1/2 z-20 hidden h-6 w-6 -translate-y-1/2 translate-x-1/2 items-center justify-center rounded-full border border-border bg-background md:flex"
                  >
                    <ArrowRight className="h-3 w-3 text-muted-foreground" />
                  </div>
                ) : null}
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
