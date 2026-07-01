"use client"

import Link from "next/link"
import { cn } from "@/lib/utils"
import { ArrowRight, Brain, Cpu, Sparkle } from "@phosphor-icons/react"

export type LearningSurfaceId = "org-learning" | "agent-training" | "model-registry"

const SURFACES: Array<{
  id: LearningSurfaceId
  href: string
  title: string
  summary: string
  icon: typeof Brain
}> = [
  {
    id: "org-learning",
    href: "/admin/intelligence",
    title: "Org Learning",
    summary: "Automatic learning from usage — queries, memory promotion, search quality.",
    icon: Sparkle,
  },
  {
    id: "agent-training",
    href: "/training",
    title: "Agent Training",
    summary: "Fine-tune agents with datasets, jobs, and custom instructions.",
    icon: Brain,
  },
  {
    id: "model-registry",
    href: "/models",
    title: "Model Registry",
    summary: "Production ML — register, deploy, and serve models in workflows.",
    icon: Cpu,
  },
]

export function LearningSurfacesCallout({
  current,
  className,
}: {
  current: LearningSurfaceId
  className?: string
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-dashed border-border bg-secondary/30 p-4",
        className,
      )}
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Three learning surfaces — pick the right one
      </p>
      <div className="mt-3 grid gap-3 md:grid-cols-3">
        {SURFACES.map((surface) => {
          const Icon = surface.icon
          const isCurrent = surface.id === current
          return (
            <div
              key={surface.id}
              className={cn(
                "rounded-lg border p-3 text-sm",
                isCurrent
                  ? "border-primary/40 bg-primary/5 ring-1 ring-primary/20"
                  : "border-border bg-background/60",
              )}
            >
              <div className="flex items-center gap-2">
                <Icon className="h-4 w-4 shrink-0 text-primary" weight="duotone" aria-hidden />
                <span className="font-medium text-foreground">{surface.title}</span>
                {isCurrent ? (
                  <span className="ml-auto rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-semibold uppercase text-primary">
                    You are here
                  </span>
                ) : null}
              </div>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground text-pretty">
                {surface.summary}
              </p>
              {!isCurrent ? (
                <Link
                  href={surface.href}
                  className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                >
                  Open {surface.title}
                  <ArrowRight className="h-3 w-3" aria-hidden />
                </Link>
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}
