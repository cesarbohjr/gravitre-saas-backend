"use client"

import Link from "next/link"
import { cn } from "@/lib/utils"
import { ArrowRight, ChatCircle, MagnifyingGlass, RocketLaunch } from "@phosphor-icons/react"
import {
  AI_WORK_SURFACES,
  type AiWorkSurfaceId,
} from "@/lib/ai-work-surfaces"

const SURFACE_ICONS = {
  "command-center": RocketLaunch,
  "workspace-chat": ChatCircle,
  "universal-search": MagnifyingGlass,
} as const

export function AiWorkSurfacesCallout({
  current,
  className,
  compact = false,
}: {
  current: AiWorkSurfaceId
  className?: string
  compact?: boolean
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-dashed border-border bg-secondary/30",
        compact ? "p-3" : "p-4",
        className,
      )}
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Three AI surfaces — not one master chat
      </p>
      {!compact ? (
        <p className="mt-1 text-xs text-muted-foreground text-pretty">
          Each page has a different job. Pick the surface that matches what you need right now.
        </p>
      ) : null}
      <div className={cn("grid gap-3", compact ? "mt-2 md:grid-cols-3" : "mt-3 md:grid-cols-3")}>
        {AI_WORK_SURFACES.map((surface) => {
          const Icon = SURFACE_ICONS[surface.id]
          const isCurrent = surface.id === current
          return (
            <div
              key={surface.id}
              className={cn(
                "rounded-lg border text-sm",
                compact ? "p-2.5" : "p-3",
                isCurrent
                  ? "border-primary/40 bg-primary/5 ring-1 ring-primary/20"
                  : "border-border bg-background/60",
              )}
            >
              <div className="flex items-center gap-2">
                <Icon className="h-4 w-4 shrink-0 text-primary" weight="duotone" aria-hidden />
                <span className="font-medium text-foreground">{surface.title}</span>
                <span className="rounded bg-muted/80 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {surface.badge}
                </span>
                {isCurrent ? (
                  <span className="ml-auto rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-semibold uppercase text-primary">
                    Here
                  </span>
                ) : null}
              </div>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground text-pretty">
                {surface.summary}
              </p>
              <p className="mt-1 text-[11px] italic text-muted-foreground/80 text-pretty">
                {surface.notThis}
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
